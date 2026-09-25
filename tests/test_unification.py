"""End-to-end and integration tests for Unified Tutuco Clip Miner features:
- Cloud status & storage
- Role-based authentication & session
- Authenticated radar webhook
- Edited video upload workflow
- Telegram publishing integration
"""
import io
import json
import os
import re
from unittest.mock import patch

import pytest
from app import create_app


@pytest.fixture
def app_and_client(tmp_path):
    # Set up test app with isolated temp data directory
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["RADAR_WEBHOOK_SECRET"] = "test-radar-secret-123"
    os.environ["AUTH_REQUIRED"] = "false"
    os.environ["ADMIN_PASSWORD"] = "TestAdminPass123!"

    app = create_app(data=str(data_dir))
    app.config["TESTING"] = True
    client = app.test_client()

    # Grab CSRF token
    res = client.get("/")
    token_match = re.search(r'name="miner-token" content="([^"]+)"', res.text)
    token = token_match[1] if token_match else ""

    yield app, client, data_dir, token

    os.environ.pop("ADMIN_PASSWORD", None)
    from miner.auth import get_user_store
    get_user_store().reload_from_env()


def test_cloud_status_endpoint(app_and_client):
    app, client, _, _ = app_and_client
    res = client.get("/api/product/cloud-status")
    assert res.status_code == 200
    data = res.get_json()
    assert "storage_mode" in data
    assert data["storage_mode"] in ("local", "gcs")
    assert "firestore_connected" in data
    assert "telegram_configured" in data
    assert "current_user" in data


def test_auth_flow(app_and_client):
    app, client, _, _ = app_and_client
    # Test invalid login
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401

    # Test valid login with configured test admin password
    res = client.post("/api/auth/login", json={"username": "admin", "password": "TestAdminPass123!"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["user"]["role"] == "Admin"

    # Test auth/me
    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    assert res_me.get_json()["user"]["username"] == "admin"

    # Test logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.get_json()["ok"] is True


def test_webhook_radar_authentication_and_ingestion(app_and_client):
    app, client, _, _ = app_and_client

    # 1. Unauthenticated request without secret should fail
    payload = {
        "channel": "gabepeixe",
        "platform": "kick",
        "category": "Minecraft",
        "hook": "Momento incrível no servidor!",
        "context": "Gabepeixe encontrou diamante e quase caiu na lava",
        "score": 92.0,
    }
    res_unauth = client.post("/api/webhook/radar", json=payload, headers={"X-Radar-Secret": "wrong-secret"})
    assert res_unauth.status_code == 401

    # 2. Authenticated request with correct secret should succeed
    res_auth = client.post(
        "/api/webhook/radar",
        json=payload,
        headers={"X-Radar-Secret": "test-radar-secret-123"},
    )
    assert res_auth.status_code == 201
    resp_data = res_auth.get_json()
    assert resp_data["status"] == "success"
    clip_id = resp_data["id"]
    assert clip_id is not None

    # Verify candidate is stored in SQLite
    store = app.extensions["miner"].store
    cand = store.candidate(clip_id)
    assert cand is not None
    assert cand["score"] == 92.0
    assert cand["status"] == "NOVO"

    # Candidate data is unpacked by store.candidate()
    assert cand["editorial_review"]["classification"] == "RECOMENDADO"
    assert "diamante" in cand["summary"]


def test_upload_edited_clip_and_serve(app_and_client):
    app, client, data_dir, token = app_and_client
    store = app.extensions["miner"].store
    headers = {"X-Miner-Token": token}

    # Create dummy VOD and Candidate first
    vod_id = "test_vod_100"
    clip_id = "test_clip_100"
    with store.connect() as db:
        db.execute(
            "INSERT INTO vods (id, campaign, source_key, data) VALUES (?, ?, ?, ?)",
            (vod_id, "gabepeixe", "2026-09-25", json.dumps({"title": "Test VOD", "creator": "gabepeixe"})),
        )
        db.execute(
            "INSERT INTO candidates (id, vod_id, start, end, score, status, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clip_id, vod_id, 10.0, 45.0, 88.0, "APROVADO", json.dumps({"title": "Clip Test"})),
        )

    # Fake mp4 file upload
    fake_video_bytes = b"\x00\x00\x00 ftypisom\x00\x00\x02\x00"
    file_data = {
        "video": (io.BytesIO(fake_video_bytes), "final_clip_edited.mp4"),
        "notes": "Edição concluída com legendas e lower terc",
        "title": "Corte Final GabePeixe",
    }

    res_upload = client.post(
        f"/api/product/clip/{clip_id}/upload-edited",
        data=file_data,
        content_type="multipart/form-data",
        headers=headers,
    )
    assert res_upload.status_code == 200
    upload_json = res_upload.get_json()
    assert upload_json["ok"] is True
    assert upload_json["status"] == "PRONTO_PARA_POSTAR"
    assert upload_json["edited_video"]["filename"] == "final_clip_edited.mp4"

    # Verify candidate updated in SQLite
    updated_cand = store.candidate(clip_id)
    assert updated_cand["status"] == "PRONTO_PARA_POSTAR"
    assert "edited_video" in updated_cand
    assert updated_cand["edited_video"]["title"] == "Corte Final GabePeixe"

    # Test downloading/serving the edited media
    relative_url = upload_json["edited_video"]["url"]
    res_serve = client.get(relative_url)
    assert res_serve.status_code == 200
    assert res_serve.data == fake_video_bytes


def test_clip_send_telegram_endpoint(app_and_client):
    app, client, _, token = app_and_client
    store = app.extensions["miner"].store
    telegram_svc = app.extensions["telegram"]
    headers = {"X-Miner-Token": token}

    vod_id = "test_vod_tg"
    clip_id = "test_clip_tg"
    with store.connect() as db:
        db.execute(
            "INSERT INTO vods (id, campaign, source_key, data) VALUES (?, ?, ?, ?)",
            (vod_id, "gabepeixe", "2026-09-25", json.dumps({"title": "Test VOD TG"})),
        )
        db.execute(
            "INSERT INTO candidates (id, vod_id, start, end, score, status, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                clip_id,
                vod_id,
                5.0,
                30.0,
                90.0,
                "PRONTO_PARA_POSTAR",
                json.dumps({
                    "title": "Clip Telegram Test",
                    "edited_video": {"url": "/media/edited/test.mp4", "storage_mode": "local", "path": ""},
                }),
            ),
        )

    # When not configured, should return 400 with helpful error
    telegram_svc.bot_token = ""
    res_unconf = client.post(f"/api/product/clip/{clip_id}/send-telegram", headers=headers)
    assert res_unconf.status_code == 400
    assert "não está configurado" in res_unconf.get_json()["error"]

    # When configured, should call send_message or send_video
    telegram_svc.bot_token = "mock_bot_token"
    telegram_svc.chat_id = "mock_chat_id"
    with patch.object(telegram_svc, "send_video", return_value={"ok": True, "result": {"message_id": 123}}):
        res_tg = client.post(f"/api/product/clip/{clip_id}/send-telegram", headers=headers)
        assert res_tg.status_code == 200
        assert res_tg.get_json()["ok"] is True
