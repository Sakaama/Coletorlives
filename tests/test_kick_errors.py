import re

import pytest

from app import create_app
from miner.errors import KICK_VOD_MESSAGE, present_job


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [kick:vod] abc: HTTP Error 404: Not Found",
        "ERROR: [Kick:VOD] abc: Unable to download JSON metadata: HTTP Error 404: Not Found",
    ],
)
def test_exact_kick_failure_is_presented_without_mutating_history(message):
    job = {"state": "ERRO", "message": message, "id": "original"}
    result = present_job(job)
    assert result["message"] == KICK_VOD_MESSAGE
    assert result["fallback"] == "import_local"
    assert result["error_code"] == "kick_vod_incompatible"
    assert job["message"] == message


@pytest.mark.parametrize(
    "message",
    [
        "[kick:vod] HTTP Error 403: Forbidden",
        "[kick:vod] HTTP Error 500",
        "[youtube] HTTP Error 404: Not Found",
        "[kick:live] HTTP Error 404: Not Found",
        "HTTP Error 404: Not Found",
        "[kick:vod] Connection timed out",
    ],
)
def test_other_errors_keep_existing_behavior(message):
    job = {"state": "ERRO", "message": message}
    assert present_job(job) == job


@pytest.mark.parametrize("campaign", ["gabepeixe", "brkk", "brabox"])
@pytest.mark.parametrize("kind", ["metadata", "download"])
def test_kick_fallback_preserves_vod_and_links_local_file(tmp_path, monkeypatch, campaign, kind):
    app = create_app(tmp_path / "data")
    client = app.test_client()
    service = app.extensions["miner"]
    original = {
        "url": "https://kick.com/brabox/videos/fixture",
        "platform": "Kick",
        "title": "Título já obtido",
        "date": "2026-09-18",
        "duration": 10,
        "eligibility": {"status": "REVISÃO HUMANA", "reasons": ["Conferir origem"]},
    }
    vod, _ = service.create_vod(campaign, original["url"], original)
    vid = vod["id"]
    preserved = service.store.dirs(campaign, vid)["transcripts"] / "existing.json"
    preserved.write_text("[]", encoding="utf-8")
    service.store.execute(
        "INSERT INTO candidates(id,vod_id,start,end,score,status,data) VALUES(?,?,1,4,60,'APROVADO','{}')",
        ("candidate", vid),
    )
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs.get("download"))
        raise ValueError("ERROR: [kick:vod] fixture: HTTP Error 404: Not Found")

    monkeypatch.setattr("miner.service.ytdlp_cli.extract_info", fail)
    jid = service.submit(vid, kind, lambda p: getattr(service, kind)(vid, p))
    service.executor.shutdown(wait=True)
    assert len(calls) == 1  # no custom retry/downloader added
    job = next(j for j in client.get("/api/state").json["jobs"] if j["id"] == jid)
    assert job["message"] == KICK_VOD_MESSAGE and job["fallback"] == "import_local"
    assert "kick:vod" in service.store.rows("SELECT message FROM jobs WHERE id=?", (jid,))[0]["message"]
    for key, value in original.items():
        assert service.store.get_vod(vid)[key] == value
    assert preserved.read_text(encoding="utf-8") == "[]"
    assert service.store.candidate("candidate")["status"] == "APROVADO"

    path = tmp_path / "manual.mp4"
    path.write_bytes(b"fixture-file")
    monkeypatch.setattr(
        "miner.media.probe", lambda p: {"duration": 10, "width": 640, "height": 360, "has_audio": True}
    )
    token = re.search('name="miner-token" content="([^"]+)"', client.get("/").text)[1]
    response = client.post(
        "/api/import/local",
        json={"campaign": campaign, "existing": vid, "path": str(path)},
        headers={"X-Miner-Token": token},
    )
    assert response.status_code == 200
    updated = response.json["vod"]
    assert updated["id"] == vid and updated["title"] == original["title"]
    assert updated["url"] == original["url"] and updated["campaign"] == campaign
    assert updated["local_path"] == str(path.resolve())
    assert len(client.get("/api/state").json["vods"]) == 1
    assert service.store.candidate("candidate")["status"] == "APROVADO"
    assert path.read_bytes() == b"fixture-file" and preserved.exists()
