import hashlib
import json
import re
from pathlib import Path

import pytest

from app import ROOT, create_app
from miner import analysis, media
from miner.rules import eligibility, load_campaigns, validate_url
from miner.service import Service, number


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    folder = tmp_path_factory.mktemp("media")
    target = folder / "fixture.mp4"
    media.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=24:duration=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=8",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ],
        target,
    )
    return target


def test_urls():
    assert validate_url("https://youtu.be/abcdefghijk?t=33")[1].endswith("v=abcdefghijk")
    assert validate_url("https://www.youtube.com/live/abcdefghijk")[0] == "YouTube"
    assert validate_url("https://kick.com/brkk/videos/1234-abcd")[0] == "Kick"
    for url in (
        "https://evil.com/test",
        "file:///C:/abc.mp4",
        "https://youtube.com.evil.com/watch?v=abcdefghijk",
        "https://kick.com/brkk",
        "https://youtube.com/playlist?list=test",
        "https://127.0.0.1/a",
    ):
        with pytest.raises(ValueError):
            validate_url(url)


def test_campaign_boundaries():
    campaigns = load_campaigns(ROOT / "config/campaigns")
    brkk = campaigns["brkk"]
    base = {
        "platform": "Kick",
        "date": "2026-09-15",
        "date_kind": "live",
        "was_live": True,
        "channel": "BRKK",
        "channel_id": "trusted",
    }
    assert eligibility(brkk, base)["status"] == "REVISÃO HUMANA"
    verified = {**brkk, "verified_channel_ids": ["trusted"]}
    assert eligibility(verified, base)["status"] == "PERMITIDA"
    assert eligibility(verified, {**base, "date": "2026-09-14"})["status"] == "NÃO PERMITIDA"
    assert eligibility(verified, {**base, "title": "Cinefy hoje"})["status"] == "PERMITIDA"
    assert eligibility(verified, {**base, "channel": "Cinefy"})["status"] == "NÃO PERMITIDA"
    assert (
        eligibility(verified, {**base, "date": "2026-09-14", "date_kind": "upload"})["status"]
        == "REVISÃO HUMANA"
    )
    gabe = {**campaigns["gabepeixe"], "verified_channel_ids": ["trusted"]}
    for date in ("2026-09-01", "2026-10-22"):
        assert eligibility(gabe, {**base, "date": date})["status"] == "PERMITIDA"
    assert eligibility(gabe, {**base, "date": "2026-08-31"})["status"] == "NÃO PERMITIDA"
    assert eligibility(gabe, {**base, "date": "2026-10-23"})["status"] == "NÃO PERMITIDA"
    assert eligibility(brkk, {"platform": "Local"})["status"] == "REVISÃO HUMANA"


def test_selective_detection_and_low_priority_silent_peaks():
    energies = [0.001] * 18000
    energies[123] = 0.9
    result = analysis.detect([], energies, 18000)
    assert result == []
    result = analysis.detect([], energies, 18000, mode="agressivo")
    assert any(c["start"] <= 123 <= c["end"] and "pico" in c["reason"] for c in result)
    assert all(0 <= c["score"] <= 100 and 0 <= c["start"] < c["end"] <= 18000 for c in result)
    result = analysis.detect(
        [
            {
                "start": 2,
                "end": 6,
                "text": "Olha isso, meu Deus! Não acredito, finalmente eu ganhei aquela partida impossível!",
            }
        ],
        [0.01] * 8,
        8,
    )
    assert result[0]["score"] > 50
    assert "reação" in result[0]["reason"]
    assert analysis.detect([], [], 5) == []


def test_validation():
    for value in ("nan", "inf", -1, 121):
        with pytest.raises(ValueError):
            number(value, 0, 120, "Pré-roll")
    with pytest.raises(ValueError):
        media.validate_rect({"x": 0, "y": 0, "width": 641, "height": 200}, 640, 360)


def test_real_media_and_history(tmp_path, video):
    service = Service(ROOT, tmp_path / "data")
    original = hashlib.sha256(video.read_bytes()).hexdigest()
    imported = service.import_local("brkk", str(video), "Fixture local", "2026-09-18")
    vid = imported["vod"]["id"]
    assert service.import_local("brkk", str(video))["known"]
    service.analyze(vid, {"transcribe": False}, lambda *a: None)
    candidates = service.store.candidates(vid)
    assert candidates == []  # a synthetic tone is not a content event
    service.store.execute(
        "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES(?,?,1,4,60,?)",
        ("export-fixture", vid, json.dumps({"reason": "fixture de exportação", "summary": "teste"})),
    )
    cid = "export-fixture"
    service.store.execute("UPDATE candidates SET start=1,end=4 WHERE id=?", (cid,))
    with pytest.raises(ValueError, match="Aprove"):
        service.export(vid, [cid], "raw", 0, 0, lambda *a: None)
    service.store.execute("UPDATE candidates SET status='APROVADO' WHERE id=?", (cid,))
    service.export(vid, [cid], "preview", 0, 0, lambda *a: None)
    service.export(vid, [cid], "raw", 0, 0, lambda *a: None)
    raw = service.store.rows("SELECT * FROM exports WHERE kind='raw'")[0]
    before = hashlib.sha256(Path(raw["path"]).read_bytes()).hexdigest()
    assert abs(media.probe(raw["path"])["duration"] - 3) < 0.2
    service.store.update_vod(vid, camera={"x": 0, "y": 0, "width": 320, "height": 240})
    service.export(vid, [cid], "prep", 0, 0, lambda *a: None)
    prep = service.store.rows("SELECT * FROM exports WHERE kind='prep'")[0]
    info = media.probe(prep["path"])
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(info["duration"] - 3) < 0.2
    assert hashlib.sha256(Path(raw["path"]).read_bytes()).hexdigest() == before
    assert hashlib.sha256(video.read_bytes()).hexdigest() == original
    assert service.store.candidates(vid)[0]["duplicate"]
    service.analyze(vid, {"transcribe": False}, lambda *a: None)
    assert service.store.candidate(cid)["status"] == "APROVADO"
    assert all(p.exists() for p in service.store.dirs("gabepeixe").values())
    service.executor.shutdown()


def test_http_jobs_security_and_restart(tmp_path, video):
    app = create_app(tmp_path / "db")
    client = app.test_client()
    service = app.extensions["miner"]
    html = client.get("/").text
    token = re.search('name="miner-token" content="([^"]+)"', html)[1]
    headers = {"X-Miner-Token": token}
    assert client.post("/api/import/local", json={}).status_code == 403
    assert (
        client.post(
            "/api/import/local", json={}, headers={**headers, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    response = client.post(
        "/api/import/local", json={"campaign": "gabepeixe", "path": str(video)}, headers=headers
    )
    assert response.status_code == 200
    vid = response.json["vod"]["id"]
    response = client.post(
        f"/api/vods/{vid}/action", json={"kind": "analyze", "transcribe": False}, headers=headers
    )
    jid = response.json["job"]
    service.executor.shutdown(wait=True)
    assert service.store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]["state"] == "CONCLUÍDO"
    assert client.get(f"/api/vods/{vid}").json["candidates"] == []
    assert client.get(f"/api/vods/{vid}").json["vod"]["analyzed"]
    assert client.get("/api/health").status_code == 200
    service.store.execute(
        "INSERT INTO jobs(id,vod_id,kind,state) VALUES('stale',?,'analyze','EXECUTANDO')", (vid,)
    )
    restarted = Service(ROOT, tmp_path / "db")
    assert restarted.store.rows("SELECT state FROM jobs WHERE id='stale'")[0]["state"] == "INTERROMPIDO"
    restarted.executor.shutdown()


def test_metadata_failure_preserves_record(tmp_path, monkeypatch):
    service = Service(ROOT, tmp_path / "data")

    def fail(*args, **kwargs):
        raise ValueError("Fonte indisponível — teste controlado")

    monkeypatch.setattr("miner.service.ytdlp_cli.extract_info", fail)
    imported = service.import_url("brkk", "https://kick.com/brkk/videos/fixture-test")
    service.executor.shutdown(wait=True)
    assert service.store.get_vod(imported["vod"]["id"])["url"]
    assert service.store.rows("SELECT state FROM jobs")[0]["state"] == "ERRO"


def test_transcript_checkpoint(tmp_path, monkeypatch):
    directory = tmp_path / "transcripts" / "base"
    directory.mkdir(parents=True)
    saved = [{"start": 1, "end": 2, "text": "Pronto"}]
    (directory / "transcript.json").write_text(json.dumps(saved), encoding="utf-8")
    import faster_whisper

    monkeypatch.setattr(
        faster_whisper, "WhisperModel", lambda *a, **k: pytest.fail("Não deveria carregar modelo")
    )
    assert analysis.transcribe("not-needed.wav", directory.parent, tmp_path, 5) == saved


def test_single_instance_lock(tmp_path):
    from miner.instance import acquire

    path = tmp_path / "instance.lock"
    first = acquire(path)
    assert first is not None
    assert acquire(path) is None
    first.close()
    second = acquire(path)
    assert second is not None
    second.close()


def test_gabe_placeholder_prep(tmp_path, video):
    preset = load_campaigns(ROOT / "config/campaigns")["gabepeixe"]["vertical"]
    raw = tmp_path / "short.mp4"
    media.clip(video, raw, 1, 2)
    target = tmp_path / "gabe.mp4"
    media.prep(
        raw,
        target,
        {"x": 0, "y": 0, "width": 320, "height": 240},
        {"x": 0, "y": 0, "width": 640, "height": 360},
        preset,
        1,
    )
    assert media.probe(target)["height"] == 1920
    assert "PLACEHOLDER" in target.with_suffix(".txt").read_text(encoding="utf-8")


def test_metadata_success_uses_live_date(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    monkeypatch.setattr(
        "miner.service.ytdlp_cli.extract_info",
        lambda *a, **k: {
            "title": "Live BRKK",
            "channel": "BRKK",
            "channel_id": "123",
            "duration": 60,
            "was_live": True,
            "release_timestamp": datetime(2026, 9, 18, 18, tzinfo=UTC).timestamp(),
            "upload_date": "20260919",
        },
    )
    service = Service(ROOT, tmp_path / "data")
    result = service.import_url("brkk", "https://youtu.be/abcdefghijk")
    service.executor.shutdown(wait=True)
    vod = service.store.get_vod(result["vod"]["id"])
    assert vod["date"] == "2026-09-18"
    assert vod["date_kind"] == "live"
    assert vod["duration"] == 60
    assert not vod.get("local_path")
