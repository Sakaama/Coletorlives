import json
import re
import pytest

from app import ROOT, create_app
from miner import backlog
from miner.collector import Collector
from miner.service import Service


def metadata(i=1, day="2026-09-16", time_str="18:00:00", creator="gabepeixe"):
    return dict(
        id=str(i),
        webUrl=f"https://kick.com/{creator}/videos/{i}",
        kind="vod",
        channel=creator,
        title=f"Live GabePeixe {i}",
        startTime=f"{day} {time_str}",
        durationSec=3600,
    )


class FakeProvider:
    def __init__(self, rows=None):
        self.rows = rows or [metadata()]
        self.calls = []

    def discover(self, *args):
        return self.rows

    def metadata(self, url, **kwargs):
        return next(row for row in self.rows if row["webUrl"] == url)


@pytest.fixture
def collector(tmp_path):
    service = Service(ROOT, tmp_path / "data")
    result = Collector(service, FakeProvider(), tmp_path / "TUTUCO-TV/04_RAW")
    yield result
    service.executor.shutdown(wait=True)


def configure(c, creator="gabepeixe"):
    return c.configure(dict(
        creator=creator,
        provider="Kick",
        channel=creator,
        start="2026-09-01",
        end="2026-09-30",
    ))["id"]


def test_sort_backlog_vods_newest_first():
    vods = [
        {"id": "v1", "date": "2026-09-02", "date_time": "2026-09-02T10:00:00"},
        {"id": "v2", "date": "2026-09-23", "date_time": "2026-09-23T20:00:00"},
        {"id": "v3", "date": "2026-09-15", "date_time": "2026-09-15T15:00:00"},
        {"id": "v4", "date": "2026-09-23", "date_time": "2026-09-23T08:00:00"},
    ]
    sorted_vods = backlog.sort_backlog_vods(vods)
    ids = [v["id"] for v in sorted_vods]
    assert ids == ["v2", "v4", "v3", "v1"], f"Expected newest first, got {ids}"


def test_filter_backlog_period():
    vods = [
        {"id": "v0", "date": "2026-08-31"},
        {"id": "v1", "date": "2026-09-01"},
        {"id": "v2", "date": "2026-09-15"},
        {"id": "v3", "date": "2026-10-01"},
        {"id": "v4", "date": "2026-10-05"},
    ]
    filtered = backlog.filter_backlog_period(vods, min_date="2026-09-01", max_date="2026-09-30")
    assert [v["id"] for v in filtered] == ["v1", "v2"]


def test_get_backlog_state():
    assert backlog.get_backlog_state({"remote_state": "CONCLUÍDO"}) == "CONCLUÍDO"
    assert backlog.get_backlog_state({"remote_state": "PENDENTE", "analyzed": True}, candidates_count=5) == "CONCLUÍDO"
    assert backlog.get_backlog_state({"remote_state": "ERRO"}) == "ERRO"
    assert backlog.get_backlog_state({"remote_state": "BLOQUEADO"}) == "BLOQUEADO"
    assert backlog.get_backlog_state({"remote_state": "EXECUTANDO"}) == "EXECUTANDO"
    assert backlog.get_backlog_state({"remote_state": "PENDENTE"}) == "PENDENTE"


def test_backlog_queue_view_and_api(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()
    c = app.extensions["collector"]
    c.provider = FakeProvider([
        metadata(1, day="2026-09-10", time_str="12:00:00"),
        metadata(2, day="2026-09-20", time_str="14:00:00"),
        metadata(3, day="2026-09-22", time_str="16:00:00"),
    ])

    token = re.search(r'name="miner-token" content="([^"]+)"', client.get("/").text)[1]
    headers = {"X-Miner-Token": token}

    body = dict(creator="gabepeixe", provider="Kick", channel="gabepeixe", start="2026-09-01", end="2026-09-30")
    res = client.post("/api/remote/campaigns", json=body, headers=headers)
    rid = res.json["campaign"]["id"]

    c.sync(rid, lambda: None, lambda *a: None)

    # Mark latest VOD (2026-09-22) as completed with candidates
    members = c.members(rid)
    assert members[0]["date"] == "2026-09-22"
    latest_id = members[0]["id"]
    c.store.update_vod(latest_id, remote_state="CONCLUÍDO")
    c.store.execute(
        "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES(?,?,?,?,?,?)",
        ("c_test", latest_id, 10, 40, 85, json.dumps({"type": "VISUAL", "summary": "corte"}))
    )

    resp = client.get(f"/api/remote/{rid}/backlog", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()

    bl = data["backlog"]
    assert bl["total_found"] == 3
    assert bl["completed_count"] == 1
    assert bl["pending_count"] == 2
    assert bl["shortlists_ready"] == 1
    assert bl["candidates_waiting"] == 1
    assert len(bl["upcoming"]) == 2
    # Check ordering in upcoming: 2026-09-20 comes before 2026-09-10
    assert bl["upcoming"][0]["date"] == "2026-09-20"
    assert bl["upcoming"][1]["date"] == "2026-09-10"

    app.extensions["miner"].executor.shutdown()


def test_backlog_runner_deduplication_and_order(collector, monkeypatch):
    c = collector
    rid = configure(c)
    c.provider.rows = [
        metadata(1, day="2026-09-05"),
        metadata(2, day="2026-09-21"),
        metadata(3, day="2026-09-12"),
    ]
    c.sync(rid, lambda: None, lambda *a: None)

    # Pre-mark 2026-09-21 as already completed
    members = c.members(rid)
    v21 = next(v for v in members if v["date"] == "2026-09-21")
    c.store.update_vod(v21["id"], remote_state="CONCLUÍDO")

    analyzed_calls = []
    def mock_analyze(vid, *args, **kwargs):
        analyzed_calls.append(vid)
        c.store.update_vod(vid, remote_state="CONCLUÍDO")
    monkeypatch.setattr(c, "analyze", mock_analyze)

    # Run backlog
    result = backlog.run_backlog(
        c, rid, {},
        check=lambda: None,
        progress=lambda *a: None,
        pause_check=lambda: False,
    )

    assert "2 VOD(s) processada(s)" in result
    # v21 must NOT be in analyzed_calls (deduplication)
    assert v21["id"] not in analyzed_calls
    # Remaining VODs must be processed in order: 2026-09-12 then 2026-09-05
    v12 = next(v for v in members if v["date"] == "2026-09-12")
    v05 = next(v for v in members if v["date"] == "2026-09-05")
    assert analyzed_calls == [v12["id"], v05["id"]]


def test_failure_isolation_runner_continues(collector, monkeypatch):
    c = collector
    rid = configure(c)
    c.provider.rows = [
        metadata(1, day="2026-09-10"),
        metadata(2, day="2026-09-20"),
    ]
    c.sync(rid, lambda: None, lambda *a: None)

    members = c.members(rid)
    v_newer = members[0]  # 2026-09-20
    v_older = members[1]  # 2026-09-10

    # Fail v_newer, succeed v_older
    def mock_analyze(vid, *args, **kwargs):
        if vid == v_newer["id"]:
            raise ValueError("Falha temporária de rede Kick")
        c.store.update_vod(vid, remote_state="CONCLUÍDO")
    monkeypatch.setattr(c, "analyze", mock_analyze)

    result = backlog.run_backlog(
        c, rid, {},
        check=lambda: None,
        progress=lambda *a: None,
        pause_check=lambda: False,
    )

    assert "1 VOD(s) com falha" in result
    assert "1 VOD(s) processada(s)" in result

    # v_newer is in ERRO state with message
    v_newer_state = c.store.get_vod(v_newer["id"])
    assert v_newer_state["remote_state"] == "ERRO"
    assert "Falha temporária de rede Kick" in v_newer_state["remote_error"]

    # v_older succeeded
    v_older_state = c.store.get_vod(v_older["id"])
    assert v_older_state["remote_state"] == "CONCLUÍDO"

    # Retry v_newer
    c.retry_vod(rid, v_newer["id"])
    assert c.store.get_vod(v_newer["id"])["remote_state"] == "PENDENTE"


def test_safe_pause_between_vod_units(collector, monkeypatch):
    c = collector
    rid = configure(c)
    c.provider.rows = [
        metadata(1, day="2026-09-10"),
        metadata(2, day="2026-09-20"),
    ]
    c.sync(rid, lambda: None, lambda *a: None)

    analyzed = []
    pause_flag = [False]
    def mock_analyze(vid, *args, **kwargs):
        analyzed.append(vid)
        c.store.update_vod(vid, remote_state="CONCLUÍDO")
        # Request pause right after first VOD finishes
        pause_flag[0] = True
    monkeypatch.setattr(c, "analyze", mock_analyze)

    result = backlog.run_backlog(
        c, rid, {},
        check=lambda: None,
        progress=lambda *a: None,
        pause_check=lambda: pause_flag[0],
    )

    assert "pausado com segurança" in result.lower()
    assert len(analyzed) == 1
    # Only the first (newer) VOD was processed, second remains pending
    members = c.members(rid)
    assert c.store.get_vod(members[0]["id"])["remote_state"] == "CONCLUÍDO"
    assert c.store.get_vod(members[1]["id"])["remote_state"] == "PENDENTE"


def test_dynamic_priority_new_vod_inserted_at_top(collector):
    c = collector
    rid = configure(c)
    c.provider.rows = [
        metadata(1, day="2026-09-10"),
        metadata(2, day="2026-09-15"),
    ]
    c.sync(rid, lambda: None, lambda *a: None)

    q = c.backlog_view(rid)
    assert [v["date"] for v in q["backlog"]["upcoming"]] == ["2026-09-15", "2026-09-10"]

    # Now discover a newer live from 2026-09-23
    c.provider.rows.append(metadata(3, day="2026-09-23"))
    c.sync(rid, lambda: None, lambda *a: None)

    q_updated = c.backlog_view(rid)
    assert [v["date"] for v in q_updated["backlog"]["upcoming"]] == ["2026-09-23", "2026-09-15", "2026-09-10"]
