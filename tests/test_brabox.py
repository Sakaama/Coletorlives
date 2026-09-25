import hashlib
from pathlib import Path

import pytest

from app import ROOT, create_app
from miner import media
from miner.rules import eligibility, load_campaigns, validate_url
from miner.service import Service


@pytest.fixture
def campaign():
    return load_campaigns(ROOT / "config/campaigns")["brabox"]


def test_brabox_configuration(campaign):
    assert campaign["name"] == "BRABOX"
    assert campaign["allowed_sources"] == ["Twitch", "Kick"]
    assert campaign["source_channels"] == ["https://www.twitch.tv/brabox", "https://kick.com/brabox"]
    assert campaign["hashtags"] == ["#brabox"]
    assert "kick.com/brabox" in campaign["required_texts"]
    assert campaign["vertical"]["text"] == "kick.com/brabox"
    assert campaign["vertical"]["asset"] is None
    assert campaign["official_profile"] is None
    assert campaign["period_start"] == "2026-09-07T00:00"
    assert campaign["period_end"] == "2026-10-06T23:59"
    assert campaign["date_disputed"]
    assert len(campaign["publication_platforms"]) == 6
    assert not campaign["publication_all_required"]
    assert campaign["ai_policy"] and len(campaign["prohibitions"]) == 8


@pytest.mark.parametrize("date", [None, "inválida", "2026-09-06", "2026-09-07", "2026-10-06", "2026-10-07"])
def test_brabox_dates_require_review(campaign, date):
    result = eligibility(
        campaign, {"platform": "Twitch", "date": date, "date_kind": "live", "was_live": True}
    )
    assert result["status"] == "REVISÃO HUMANA"
    assert any("divergência" in reason.lower() for reason in result["reasons"])


@pytest.mark.parametrize("platform", ["Twitch", "Kick", "Local"])
def test_brabox_sources_never_assume_authorship(campaign, platform):
    assert eligibility(campaign, {"platform": platform, "was_live": True})["status"] == "REVISÃO HUMANA"


@pytest.mark.parametrize("content_type", ["reel", "tiktok", "short", "edited_video", "third_party_clip"])
def test_brabox_excluded_content(campaign, content_type):
    assert (
        eligibility(campaign, {"platform": "Local", "content_type": content_type})["status"]
        == "NÃO PERMITIDA"
    )


def test_brabox_dates_do_not_override_source_restrictions(campaign):
    assert eligibility(campaign, {"platform": "YouTube", "date": "2026-09-18"})["status"] == "NÃO PERMITIDA"
    assert eligibility(campaign, {"platform": "Kick", "was_live": False})["status"] == "NÃO PERMITIDA"


def test_twitch_vod_validation():
    assert (
        validate_url("https://www.twitch.tv/videos/123456789?t=1h")[1]
        == "https://www.twitch.tv/videos/123456789"
    )
    assert validate_url("https://kick.com/brabox/videos/1234-abcd")[0] == "Kick"
    for url in (
        "https://twitch.tv/brabox",
        "https://clips.twitch.tv/Example",
        "https://twitch.tv/brabox/clip/Example",
        "https://twitch.tv.evil.com/videos/123",
        "https://twitch.tv/videos/not-a-vod",
    ):
        with pytest.raises(ValueError):
            validate_url(url)


def test_brabox_import_metadata_and_campaign_isolation(tmp_path, monkeypatch):
    service = Service(ROOT, tmp_path / "data")
    monkeypatch.setattr(
        "miner.service.ytdlp_cli.extract_info",
        lambda *a, **k: {
            "title": "Live original Brabox",
            "channel": "brabox",
            "duration": 120,
            "upload_date": "20260918",
        },
    )
    try:
        for old in ("gabepeixe", "brkk"):
            with pytest.raises(ValueError, match="Fonte"):
                service.import_url(old, "https://twitch.tv/videos/123456789")
        with pytest.raises(ValueError, match="Fonte"):
            service.import_url("brabox", "https://youtube.com/shorts/abcdefghijk")
        result = service.import_url("brabox", "https://twitch.tv/videos/123456789")
    finally:
        service.executor.shutdown(wait=True)
    vod = service.store.get_vod(result["vod"]["id"])
    assert vod["platform"] == "Twitch"
    assert vod["was_live"] is None  # missing metadata is not evidence of an edited video
    assert vod["eligibility"]["status"] == "REVISÃO HUMANA"
    assert all(path.exists() for path in service.store.dirs("brabox", vod["id"]).values())
    for old in ("gabepeixe", "brkk"):
        assert "Twitch" not in service.campaign(old)["allowed_sources"]
        assert not service.campaign(old).get("date_disputed")
        assert "brabox" not in service.campaign(old)["vertical"]["text"]


def test_brabox_real_prep_preserves_raw_and_camera(tmp_path):
    source = tmp_path / "source.mp4"
    media.ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=24:duration=2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
        ],
        source,
    )
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    service = Service(ROOT, tmp_path / "data")
    try:
        vod = service.import_local("brabox", str(source), date="2026-11-01")["vod"]
        assert vod["eligibility"]["status"] == "REVISÃO HUMANA"
        service.analyze(vod["id"], {"transcribe": False}, lambda *a: None)
        assert service.store.candidates(vod["id"]) == []
        service.store.execute(
            "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES(?,?,0,2,60,?)",
            ("prep-fixture", vod["id"], '{"reason":"fixture","summary":"teste PREP"}'),
        )
        c = service.store.candidates(vod["id"])[0]
        with pytest.raises(ValueError, match="Aprove"):
            service.export(vod["id"], [c["id"]], "raw", 0, 0, lambda *a: None)
        service.store.execute("UPDATE candidates SET status='APROVADO' WHERE id=?", (c["id"],))
        camera = {"x": 0, "y": 0, "width": 320, "height": 240}
        service.store.update_vod(vod["id"], camera=camera, vertical={"text_x": 50, "text_y": 685})
        service.export(vod["id"], [c["id"]], "raw", 0, 0, lambda *a: None)
        raw = Path(service.store.rows("SELECT path FROM exports WHERE kind='raw'")[0]["path"])
        raw_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
        service.export(vod["id"], [c["id"]], "prep", 0, 0, lambda *a: None)
        prep = Path(service.store.rows("SELECT path FROM exports WHERE kind='prep'")[0]["path"])
        info = media.probe(prep)
        assert (info["width"], info["height"]) == (1080, 1920)
        assert prep != raw and "prep" in prep.parts and "raw" in raw.parts
        assert prep.with_suffix(".txt").read_text(encoding="utf-8") == "kick.com/brabox"
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == raw_hash
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
        assert service.store.get_vod(vod["id"])["camera"] == camera
        media.frame(prep, tmp_path / "brabox-prep.jpg", 0.5)
    finally:
        service.executor.shutdown(wait=True)


def test_brabox_available_in_existing_api(tmp_path):
    app = create_app(tmp_path / "data")
    try:
        response = app.test_client().get("/api/state")
        assert {"brabox", "gabepeixe", "brkk"} <= set(response.json["campaigns"])
        assert "Twitch (BRABOX)" in app.test_client().get("/").text
    finally:
        app.extensions["miner"].executor.shutdown(wait=True)
