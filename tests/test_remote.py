import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import ROOT, create_app
from miner import analysis, long_vod, media
from miner.collector import Collector
from miner.remote_analysis import RemoteSource
from miner.remote_provider import Cancelled, Provider, QualityUnavailable
from miner.remote_temp import Temporaries
from miner.service import Service
from test_miner import video  # noqa: F401


def metadata(i=1, day="2026-09-16", creator="brkk"):
    return dict(id=str(i), webUrl=f"https://kick.com/{creator}/videos/{i}", kind="vod", channel=creator,
                title=f"Gameplay {i}", startTime=f"{day} 18:00:00", durationSec=1200)


class FakeProvider:
    def __init__(self):
        self.rows = [metadata()]
        self.calls = []
        self.fail = False

    def discover(self, *args):
        if self.fail:
            raise ValueError("Provider indisponível; use URL manual")
        return self.rows

    def metadata(self, url, **kwargs):
        if self.fail:
            raise ValueError("Metadados indisponíveis")
        return next(row for row in self.rows if row["webUrl"] == url)

    def download(self, url, target, start, end, quality, check, progress):
        check()
        self.calls.append((start, end, quality))
        Path(target).write_bytes(b"remote range")
        return dict(requested_start=start, requested_end=end, obtained_duration=end-start,
                    media=dict(width=1920, height=1080, fps=60, duration=end-start, has_audio=True))


@pytest.fixture
def collector(tmp_path):
    service = Service(ROOT, tmp_path / "data")
    result = Collector(service, FakeProvider(), tmp_path / "TUTUCO-TV/04_RAW")
    yield result
    service.executor.shutdown(wait=True)


def configure(c, creator="brkk"):
    return c.configure(dict(creator=creator, provider="Kick", channel=creator, start="2026-09-01", end="2026-10-01"))["id"]


def seed(c, rid, number=1, score=80, start=100):
    vid, _, _ = c.register(rid, metadata(number))
    cid = f"c{number}"
    c.store.execute("INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES(?,?,?,?,?,?)",
                    (cid, vid, start, start+35, score, json.dumps({"type": "VISUAL", "summary": "fala", "reason": "payoff"})))
    return vid, cid


def test_discovery_period_dedup_incremental_18_to_19_and_skip_completed(collector, monkeypatch):
    c = collector
    rid = configure(c)
    c.provider.rows = [metadata(i) for i in range(18)] + [metadata(90, "2026-08-31")]
    c.sync(rid, lambda: None, lambda *a: None)
    assert len(c.members(rid)) == 18
    for v in c.members(rid):
        c.store.update_vod(v["id"], remote_state="CONCLUÍDO")
    c.provider.rows.append(metadata(19))
    assert "1 nova(s)" in c.sync(rid, lambda: None, lambda *a: None)
    assert c.view(rid)["summary"]["pending"] == 1
    called = []
    monkeypatch.setattr(c, "analyze", lambda vid, *args: called.append(vid))
    c.mine(rid, {}, lambda: None, lambda *a: None)
    assert len(called) == 1
    c.sync(rid, lambda: None, lambda *a: None)
    assert len(c.members(rid)) == 19 and c.get(rid)["last_sync"]


@pytest.mark.parametrize("creator", ["gabepeixe", "brkk", "brabox"])
def test_preserves_campaign_rules_and_manual_urls(collector, creator):
    c = collector
    before = json.dumps(c.service.campaigns, sort_keys=True)
    rid = configure(c, creator)
    c.provider.rows = [metadata(1, creator=creator)]
    c.manual(rid, [c.provider.rows[0]["webUrl"]] * 2, lambda: None, lambda *a: None)
    assert len(c.members(rid)) == 1
    assert before == json.dumps(c.service.campaigns, sort_keys=True)
    if creator == "brkk":
        vid, _, _ = c.register(rid, {**metadata(2), "title": "!Cinefy"})
        assert c.store.get_vod(vid)["remote_state"] == "PENDENTE"
        c.register(rid, {**metadata(2), "channel": "cinefy"})
        with pytest.raises(ValueError, match="não permitida"):
            c.analyze(vid, {}, lambda *a: None)


def test_manual_provider_error_keeps_intent_and_completed_work(collector):
    c = collector
    rid = configure(c)
    c.provider.fail = True
    with pytest.raises(ValueError):
        c.manual(rid, [metadata()["webUrl"]], lambda: None, lambda *a: None)
    v = c.members(rid)[0]
    assert v["remote_state"] == "ERRO"
    c.store.update_vod(v["id"], remote_state="CONCLUÍDO", duration=1200)
    with pytest.raises(ValueError):
        c.manual(rid, [metadata()["webUrl"]], lambda: None, lambda *a: None)
    assert c.store.get_vod(v["id"])["remote_state"] == "CONCLUÍDO"


def test_temporary_checkpoint_disk_and_user_protection(tmp_path, monkeypatch):
    t = Temporaries(tmp_path)
    imported = tmp_path / "user.mp4"
    raw = tmp_path / "04_RAW/raw.mp4"
    raw.parent.mkdir()
    for p in (imported, raw):
        p.write_bytes(b"precious")
    lease = t.lease("vod", 21600, 22200, "scan", "analysis")
    (lease / "media.mp4").write_bytes(b"temporary")
    assert not t.clean(lease)
    t.cleanup()
    assert lease.exists()
    with pytest.raises(ValueError):
        t.commit(lease, tmp_path / "missing.json")
    checkpoint = tmp_path / "complete.json"
    analysis.save_json(checkpoint, {"complete": True})
    t.commit(lease, checkpoint)
    assert not lease.exists()
    assert imported.read_bytes() == raw.read_bytes() == b"precious"
    with pytest.raises(ValueError):
        t.clean(raw.parent)
    monkeypatch.setattr("miner.remote_temp.shutil.disk_usage", lambda p: SimpleNamespace(free=1))
    with pytest.raises(ValueError, match="Espaço insuficiente"):
        t.space(600)


def test_orphan_cleanup_requires_unchanged_checkpoint(tmp_path, monkeypatch):
    t = Temporaries(tmp_path)
    lease = t.lease("vod", 0, 600, "scan", "analysis")
    proof = tmp_path / "complete.json"
    analysis.save_json(proof, {"completed": 1})
    original = t.clean
    monkeypatch.setattr(t, "clean", lambda p: False)
    t.commit(lease, proof)
    monkeypatch.setattr(t, "clean", original)
    analysis.save_json(proof, {"changed": 1})
    t.cleanup()
    assert lease.exists()
    analysis.save_json(proof, {"completed": 1})
    Temporaries(tmp_path).cleanup()
    assert not lease.exists()


def test_remote_absolute_transcription_cache_resume_and_zero_quota(collector, monkeypatch):
    c = collector
    rid = configure(c)
    vid, _, _ = c.register(rid, {**metadata(), "durationSec": 22800})
    v = c.store.get_vod(vid)
    root = c.store.dirs(v["campaign"], vid)["transcripts"]
    adapter = RemoteSource(v, c.provider, c.temp, window=(21600, 22800))
    scans = []
    interrupt = [True]
    def scan(a, b, folder, progress):
        adapter.acquire(a, b, str(folder))
        if a == 22200 and interrupt[0]:
            raise Cancelled()
        scans.append(a)
        return {"energy": [.03] * int(b-a), "visual": []}
    monkeypatch.setattr(adapter, "scan", scan)
    monkeypatch.setattr(long_vod, "promising", lambda *a: [[21600, 22200]])
    monkeypatch.setattr(media, "extract_audio", lambda source, target, duration: Path(target).write_bytes(b"audio"))
    def speech(audio, folder, models, duration, model, device, progress):
        assert device == "cpu"
        path = Path(folder) / model / "transcript.json"
        if path.exists():
            return json.loads(path.read_text())
        rows = [{"start": 10, "end": 20, "text": "fala"}]
        path.parent.mkdir(exist_ok=True)
        analysis.save_json(path, rows)
        return rows
    monkeypatch.setattr(analysis, "transcribe", speech)
    detected = []
    def detect(rows, *args, **kwargs):
        detected.extend(rows)
        return []  # No quota: even strong visual signals must not manufacture candidates.
    monkeypatch.setattr(analysis, "detect", detect)
    def run():
        return long_vod.run(v["url"], root, ROOT / "models", {"duration": 22800, "has_audio": True}, {}, lambda *a: None, adapter)
    with pytest.raises(Cancelled):
        run()
    assert len(list(c.temp.root.iterdir())) == 1  # interrupted range is available for retry
    interrupt[0] = False
    found, warnings, metrics, _ = run()
    assert not found and not warnings and metrics["chunks_cached"] == 1
    assert scans == [21600, 22200]
    assert any(s["start"] >= 21600 for s in detected)
    before = len(c.provider.calls)
    _, _, warm, _ = run()
    assert warm["chunks_cached"] == 2 and warm["transcription_cached"] > 0
    assert len(c.provider.calls) == before
    assert not list(c.temp.root.iterdir())


def test_failure_checkpoint_releases_recreatable_chunks(collector, monkeypatch):
    c = collector
    rid = configure(c)
    vid, _, _ = c.register(rid, metadata())
    v = c.store.get_vod(vid)
    adapter = RemoteSource(v, c.provider, c.temp)
    def scan(a, b, folder, progress):
        adapter.acquire(a, b, str(folder))
        (folder / "generated.wav").write_bytes(b"recreatable PCM")
        raise ValueError("scan failed")
    monkeypatch.setattr(adapter, "scan", scan)
    result = long_vod.run(v["url"], c.store.dirs("brkk", vid)["transcripts"], ROOT / "models",
                          {"duration": 1200, "has_audio": True}, {}, lambda *a: None, adapter)
    assert result[1] and not list(c.temp.root.iterdir())
    assert list(c.store.root.rglob("checkpoint.json"))
    assert not list(c.store.root.rglob("*.wav"))


def test_aggregate_ranking_dedup_review_package_and_history(collector):
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid)
    _, other = seed(c, rid, 2, 95)
    c.store.execute("INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES('duplicate',?,101,136,79,'{}')", (vid,))
    assert [v["id"] for v in c.view(rid)["candidates"]] == [other, cid]
    c.review(rid, [cid, other], "APROVADO")
    c.package(rid, cid, dict(title="Tarja", recommended_start=98, recommended_end=140, layout="VISUAL"))
    c.service.save_analysis(vid, [dict(start=100, end=135, score=85)], [], {}, "base", "equilibrado", True)
    row = c.store.candidate(cid)
    assert row["status"] == "APROVADO" and row["editorial_package"]["title"] == "Tarja"
    assert c.view(rid)["summary"]["approved"] == 2


def test_serial_queue_approved_only_retry_cancel_and_raw_range(collector, monkeypatch):
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid)
    _, other = seed(c, rid, 2)
    with pytest.raises(ValueError, match="aprovados"):
        c.download_approved(rid, [cid, other], {})
    c.review(rid, [cid, other], "APROVADO")
    tasks = []
    monkeypatch.setattr(c.service.executor, "submit", tasks.append)
    ids = c.download_approved(rid, [cid, other], dict(pre=5, post=7))
    assert len(ids) == 2 and not c.download_approved(rid, [cid], {})
    tasks.pop(0)()
    raw = c.store.rows("SELECT * FROM exports WHERE candidate_id=?", (cid,))[0]
    assert (raw["start"], raw["end"]) == (95, 142)
    assert c.provider.calls == [(95, 142, "1080p60")]
    target = Path(raw["path"])
    assert target.parent == c.output / "BRKK"
    assert re.fullmatch(r"BRKK_2026-09-16_000140_VISUAL_c1_[a-f0-9]{6}_RAW.mp4", target.name)
    assert target.is_file() and not list(c.temp.root.iterdir())
    c.cancel(rid)
    tasks.pop(0)()
    assert c.store.rows("SELECT state FROM remote_jobs WHERE id=?", (ids[1],))[0]["state"] == "CANCELADO"
    retry = c.enqueue(rid, "raw", dict(candidate_id=other, pre=5, post=7, best=True))
    tasks.pop(0)()
    assert c.store.rows("SELECT state FROM remote_jobs WHERE id=?", (retry,))[0]["state"] == "CONCLUÍDO"
    assert c.provider.calls[-1][-1] == "best"
    assert target.is_file()


def test_restart_marks_queued_jobs_interrupted(collector, monkeypatch):
    c = collector
    rid = configure(c)
    monkeypatch.setattr(c.service.executor, "submit", lambda fn: None)
    c.enqueue(rid, "sync")
    Collector(c.service, c.provider, c.output)
    assert c.view(rid)["jobs"][0]["state"] == "INTERROMPIDO"


@pytest.mark.parametrize("height,fps,quality,ok", [(1080,60,"1080p60",True),(1080,30,"1080p60",False),(720,60,"1080p60",False),(720,30,"best",True)])
def test_provider_range_invocation_quality_and_fallback(tmp_path, monkeypatch, height, fps, quality, ok):
    p = Provider(ROOT)
    commands = []
    monkeypatch.setattr(p, "metadata", lambda *a: {"sourceUrl": "https://public.example/media.m3u8"})
    monkeypatch.setattr(p, "execute", lambda args, *a: commands.append(args))
    monkeypatch.setattr(media, "probe", lambda target: dict(duration=30, width=1920, height=height, fps=fps))
    if ok:
        assert p.download(metadata()["webUrl"], tmp_path / "cut.mp4", 21600, 21630, quality)["media"]["fps"] == fps
    else:
        with pytest.raises(QualityUnavailable):
            p.download(metadata()["webUrl"], tmp_path / "cut.mp4", 21600, 21630, quality)
    args = commands[0]
    assert args[:3] == [str(ROOT / ".venv/Scripts/python.exe"), "-m", "yt_dlp"]
    assert args[args.index("--download-sections")+1] == "*21600.000-21630.000"
    assert "--force-keyframes-at-cuts" in args
    with pytest.raises(ValueError, match="15 minutos"):
        p.download(metadata()["webUrl"], tmp_path / "whole.mp4", 0, 43200)


def test_provider_errors_and_invalid_public_source(monkeypatch):
    p = Provider(ROOT)
    with pytest.raises(ValueError, match="manualmente"):
        p.discover("Local", "brkk")
    monkeypatch.setattr(p, "metadata", lambda *a: {"sourceUrl": "file:///private"})
    with pytest.raises(ValueError, match="arquivo local"):
        p.download(metadata()["webUrl"], "unused.mp4", 0, 30)


def test_remote_api_security_membership_and_validation(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()
    token = re.search(r'name="miner-token" content="([^"]+)"', client.get("/").text)[1]
    body = dict(creator="brkk", provider="Kick", channel="brkk", start="2026-09-15", end="2026-10-01")
    assert client.post("/api/remote/campaigns", json=body).status_code == 403
    headers = {"X-Miner-Token": token}
    result = client.post("/api/remote/campaigns", json=body, headers=headers)
    rid = result.json["campaign"]["id"]
    assert client.get(f"/api/remote/{rid}").json["summary"]["found"] == 0
    for action in [dict(kind="download", ids=[]), dict(kind="manual", urls=["file:///test"]), dict(kind="retry", job="missing")]:
        assert client.post(f"/api/remote/{rid}/action", json=action, headers=headers).status_code == 400
    app.extensions["miner"].executor.shutdown()


def test_canonical_provider_id_deduplicates_alias_and_preserves_approval(collector):
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid)
    c.review(rid, [cid], "APROVADO")
    c.store.update_vod(vid, remote_state="CONCLUÍDO")
    canonical = {**metadata(), "webUrl": "https://kick.com/brkk/videos/canonical-id"}
    updated, fresh, _ = c.register(rid, canonical)
    assert updated == vid and not fresh
    assert len(c.members(rid)) == 1
    assert c.store.candidate(cid)["status"] == "APROVADO"
    assert c.store.get_vod(vid)["remote_state"] == "CONCLUÍDO"


def test_remote_preview_frame_and_existing_prep_without_full_vod(collector, monkeypatch, video):  # noqa: F811
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid, start=1)
    c.store.execute("UPDATE candidates SET end=3 WHERE id=?", (cid,))
    c.store.update_vod(vid, duration=8)
    def transfer(url, target, start, end, quality, check, progress):
        media.clip(video, target, start, end)
        return dict(media=media.probe(target), requested_start=start, requested_end=end)
    monkeypatch.setattr(c.provider, "download", transfer)
    c.export(cid, "preview", 0, 0, True, lambda *a: None)
    c.review(rid, [cid], "APROVADO")
    c.export(cid, "raw", 0, 0, True, lambda *a: None)
    raw = c.store.rows("SELECT path FROM exports WHERE kind='raw'")[0]["path"]
    before = Path(raw).read_bytes()
    c.frame(vid, 1, lambda *a: None)
    c.store.update_vod(vid, camera=dict(x=0, y=0, width=160, height=120))
    c.service.export(vid, [cid], "prep", 0, 0, lambda *a: None)
    prep = c.store.rows("SELECT path FROM exports WHERE kind='prep'")[0]["path"]
    info = media.probe(prep)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert Path(raw).read_bytes() == before and not list(c.temp.root.iterdir())
    assert not c.store.get_vod(vid).get("local_path")


def test_provider_subprocess_inherits_venv_environment_and_cwd(monkeypatch):
    observed = {}
    class Process:
        def __init__(self, args, **kwargs):
            observed.update(args=args, **kwargs)
        def wait(self, **kwargs):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr("miner.remote_provider.subprocess.Popen", Process)
    p = Provider(ROOT)
    p.execute([p.python(), "-m", "yt_dlp", "--skip-download", metadata()["webUrl"]])
    assert observed["cwd"] == str(ROOT) and observed["env"] is None and observed["shell"] is False
    assert observed["args"][:3] == [str(ROOT / ".venv/Scripts/python.exe"), "-m", "yt_dlp"]
    assert not any("proxy" in arg for arg in observed["args"])


def test_cancel_terminates_only_owned_download_process_tree(monkeypatch):
    calls = []
    class Process:
        pid = 987654
        alive = True
        def __init__(self, *args, **kwargs):
            pass
        def poll(self):
            return None if self.alive else 0
        def terminate(self):
            self.alive = False
        def wait(self):
            return 0
    monkeypatch.setattr("miner.remote_provider.subprocess.Popen", Process)
    monkeypatch.setattr("miner.remote_provider.subprocess.run", lambda args, **kwargs: calls.append(args))
    def cancel():
        raise Cancelled()
    with pytest.raises(Cancelled):
        Provider(ROOT).execute(["owned-tool"], cancel)
    assert calls == [["taskkill", "/PID", "987654", "/T", "/F"]]


def test_youtube_upload_does_not_become_verified_live(collector):
    c = collector
    rid = c.configure(dict(creator="brkk", provider="YouTube", channel="brkk", start="2026-09-15", end="2026-10-01"))["id"]
    vid, _, _ = c.register(rid, {**metadata(), "webUrl": "https://www.youtube.com/watch?v=abcdefghijk", "was_live": False, "date_kind": "upload"})
    v = c.store.get_vod(vid)
    assert v["was_live"] is False and v["date_kind"] == "upload"


@pytest.mark.parametrize("title", ["A VOLTA ... !CINEFY !APP", "Cinefy", "!APP !comandos patrocinadores promoções"])
def test_promo_metadata_never_blocks_valid_brkk_vod(collector, title):
    c = collector
    rid = configure(c)
    vid, _, _ = c.register(rid, {**metadata(), "title": title, "description": "!CINEFY !APP"})
    vod = c.store.get_vod(vid)
    assert vod["remote_state"] == "PENDENTE"
    assert vod["eligibility"]["status"] != "NÃO PERMITIDA"


def test_sync_releases_keyword_block_but_keeps_independent_restrictions(collector):
    c = collector
    rid = configure(c)
    ids = []
    for i, day in [(1, "2026-09-16"), (2, "2026-09-14")]:
        row = {**metadata(i, day), "title": "A VOLTA ... !CINEFY !APP"}
        vid, _, _ = c.register(rid, row)
        c.store.update_vod(vid, remote_state="BLOQUEADO", eligibility={"status": "NÃO PERMITIDA", "reasons": ["Referência a conteúdo excluído pela campanha (Cinefy)."]})
        ids.append(vid)
    c.provider.rows = [{**metadata(1), "title": "A VOLTA ... !CINEFY !APP"}, metadata(2, "2026-09-14")]
    c.sync(rid, lambda: None, lambda *a: None)
    assert c.store.get_vod(ids[0])["remote_state"] == "PENDENTE"
    assert c.store.get_vod(ids[1])["remote_state"] == "BLOQUEADO"
    assert "Data da live" in c.store.get_vod(ids[1])["eligibility"]["reasons"][0]
    c.store.update_vod(ids[0], remote_state="CONCLUÍDO", analyzed=True)
    c.sync(rid, lambda: None, lambda *a: None)
    assert c.store.get_vod(ids[0])["remote_state"] == "CONCLUÍDO"


def test_valid_vod_with_protected_excerpt_only_flags_candidate(collector, monkeypatch):
    c = collector
    rid = configure(c)
    vid, _, _ = c.register(rid, {**metadata(), "title": "A VOLTA ... !CINEFY !APP"})
    words = [{"start": 100, "end": 110, "text": "Olha isso, vou contar uma história. Estamos assistindo um filme."},
             {"start": 110, "end": 125, "text": "Meu Deus, não acredito! Que piada, todo mundo rindo."},
             {"start": 125, "end": 135, "text": "No final consegui, ganhei, deu certo!"}]
    found = analysis.detect(words, [.03] * 1200, 1200)
    assert found and found[0]["eligibility_review"]["status"] == "REVISÃO DE ELEGIBILIDADE"
    monkeypatch.setattr(long_vod, "run", lambda *a, **kw: (found, [], {}, True))
    c.analyze(vid, {}, lambda *a: None)
    assert c.store.get_vod(vid)["remote_state"] == "CONCLUÍDO"
    candidate = c.store.candidates(vid)[0]
    assert candidate["status"] == "NOVO"
    assert candidate["eligibility_review"]["status"] == "REVISÃO DE ELEGIBILIDADE"


@pytest.mark.parametrize("text", ["React de vídeo no YouTube e TikTok", "Gameplay com muita atividade visual", "!CINEFY !APP", "Eu gostei daquele filme e daquela série."])
def test_reacts_motion_and_promo_are_not_film_evidence(text):
    from miner.rules import candidate_eligibility
    from miner.visual_activity import rank
    assert candidate_eligibility(text) == {}
    candidate = dict(start=0, end=60, score=80, summary=text, eligibility_review={})
    assert rank([candidate], [{"time": 10, "score": 100}])[0]["eligibility_review"] == {}
