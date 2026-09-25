"""Tests for TelegramService."""
from unittest.mock import MagicMock, patch

from miner.telegram import TelegramService


def test_telegram_unconfigured():
    svc = TelegramService(bot_token="", chat_id="")
    assert not svc.is_configured

    msg_res = svc.send_message("Test message")
    assert not msg_res["ok"]
    assert "not configured" in msg_res["error"]

    vid_res = svc.send_video("http://example.com/video.mp4")
    assert not vid_res["ok"]
    assert "not configured" in vid_res["error"]


def test_telegram_send_message_mock():
    svc = TelegramService(bot_token="fake_token", chat_id="123456")
    assert svc.is_configured

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
        mock_post.return_value = mock_response

        res = svc.send_message("Olá do Tutuco Clip Miner!")
        assert res["ok"]
        assert res["result"]["message_id"] == 999
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "sendMessage" in args[0]
        assert kwargs["json"]["chat_id"] == "123456"


def test_telegram_format_publication_caption():
    candidate = {
        "headline": "Jogada Épica",
        "streamer": "GabePeixe",
        "vod_title": "Campeonato GabePeixe Dia 1",
    }
    caption_pkg = {
        "suggested_caption": "O momento em que tudo mudou!",
        "mentions": "@gabepeixe",
        "hashtags_str": "#gabepeixe #clipes",
    }

    formatted = TelegramService.format_publication_caption(candidate, caption_pkg)
    assert "Jogada Épica" in formatted
    assert "GabePeixe" in formatted
    assert "@gabepeixe" in formatted
    assert "#gabepeixe" in formatted
