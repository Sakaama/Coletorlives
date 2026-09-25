"""Telegram Service for publishing notifications and sending edited clips.

Supports optional Telegram integration via bot token and chat ID.
Provides graceful fallbacks when credentials are not configured.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests

logger = logging.getLogger("miner.telegram")


class TelegramService:
    """Service to send notifications and video clips to Telegram channels/chats."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""

    @property
    def is_configured(self) -> bool:
        """Check if both bot token and chat ID are configured."""
        return bool(self.bot_token and self.chat_id)

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a text message to the configured or specified chat."""
        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            return {
                "ok": False,
                "error": "Telegram bot_token or chat_id not configured",
                "mock": True,
            }

        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            res = requests.post(url, json=payload, timeout=15)
            data = res.json()
            if res.status_code == 200 and data.get("ok"):
                return {"ok": True, "result": data.get("result")}
            return {
                "ok": False,
                "error": data.get("description", f"HTTP {res.status_code}"),
                "details": data,
            }
        except Exception as exc:
            logger.warning(f"Failed to send Telegram message: {exc}")
            return {"ok": False, "error": str(exc)}

    def send_video(
        self,
        video_source: Union[str, Path],
        caption: str = "",
        parse_mode: str = "HTML",
        chat_id: Optional[str] = None,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """Send a video to Telegram via URL or direct file upload.
        
        Args:
            video_source: Public/Signed HTTP URL or local filesystem path.
            caption: Accompanying text / hashtags / publication package.
            parse_mode: 'HTML' or 'Markdown'.
            chat_id: Target chat ID (defaults to configured TELEGRAM_CHAT_ID).
            timeout: HTTP timeout in seconds.
        """
        target_chat = chat_id or self.chat_id
        if not self.bot_token or not target_chat:
            return {
                "ok": False,
                "error": "Telegram bot_token or chat_id not configured",
                "mock": True,
            }

        url = f"{self.api_base}/sendVideo"
        # Check if source is a URL or a local file
        video_str = str(video_source)
        is_url = video_str.startswith("http://") or video_str.startswith("https://")

        try:
            if is_url:
                payload = {
                    "chat_id": target_chat,
                    "video": video_str,
                    "caption": caption[:1024],  # Telegram caption limit is 1024 chars
                    "parse_mode": parse_mode,
                }
                res = requests.post(url, json=payload, timeout=timeout)
            else:
                local_path = Path(video_str)
                if not local_path.is_file():
                    return {
                        "ok": False,
                        "error": f"Local video file not found: {local_path}",
                    }

                data = {
                    "chat_id": target_chat,
                    "caption": caption[:1024],
                    "parse_mode": parse_mode,
                }
                with open(local_path, "rb") as video_file:
                    files = {"video": (local_path.name, video_file, "video/mp4")}
                    res = requests.post(url, data=data, files=files, timeout=timeout)

            response_data = res.json()
            if res.status_code == 200 and response_data.get("ok"):
                return {"ok": True, "result": response_data.get("result")}

            return {
                "ok": False,
                "error": response_data.get("description", f"HTTP {res.status_code}"),
                "details": response_data,
            }
        except Exception as exc:
            logger.warning(f"Failed to send Telegram video: {exc}")
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def format_publication_caption(
        candidate: Dict[str, Any],
        caption_pkg: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format an attractive publication package message for Telegram."""
        title = candidate.get("headline") or candidate.get("title") or "Corte Destacado"
        streamer = candidate.get("streamer") or candidate.get("creator_key") or "Geral"
        vod_title = candidate.get("vod_title") or ""

        hashtags = ""
        mentions = ""
        caption_text = ""

        if caption_pkg:
            hashtags = caption_pkg.get("hashtags_str", "")
            mentions = caption_pkg.get("mentions", "")
            caption_text = caption_pkg.get("suggested_caption", "")
        else:
            cand_hashtags = candidate.get("hashtags", [])
            if isinstance(cand_hashtags, list):
                hashtags = " ".join(cand_hashtags)
            elif isinstance(cand_hashtags, str):
                hashtags = cand_hashtags

        parts = [
            f"🎬 <b>{title}</b>",
            f"👤 Streamer: <b>{streamer}</b>",
        ]
        if vod_title:
            parts.append(f"📺 Origem: <i>{vod_title[:60]}</i>")

        if caption_text:
            parts.append(f"\n📝 <b>Legenda Sugerida:</b>\n{caption_text}")
        if mentions:
            parts.append(f"📌 Menções: {mentions}")
        if hashtags:
            parts.append(f"🏷️ Hashtags: {hashtags}")

        parts.append("\n✅ <i>Pronto para postar via Tutuco Clip Miner</i>")
        return "\n".join(parts)


def get_telegram_service() -> TelegramService:
    """Factory helper to obtain a TelegramService instance."""
    return TelegramService()
