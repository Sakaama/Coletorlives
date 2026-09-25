"""Ephemeral YouTube source discovery for TUTUCO CLIP MINER V2.

Decoupled from media import: discovery inspects metadata and classifies items
without writing to the database or downloading media.
"""
import json
import re
from datetime import datetime, UTC

from miner.remote_provider import youtube_source
from miner.rules import validate_url
from miner.ytdlp_cli import discovery_args


def parse_upload_date(value):
    """Normalize upload_date into YYYY-MM-DD string if possible."""
    if not value:
        return None
    val_str = str(value).strip()
    if re.fullmatch(r"\d{8}", val_str):
        try:
            return f"{val_str[:4]}-{val_str[4:6]}-{val_str[6:]}"
        except Exception:
            pass
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val_str):
        return val_str
    return None


def format_duration(seconds):
    """Format duration in seconds to mm:ss or hh:mm:ss for display."""
    if seconds is None:
        return None
    try:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except Exception:
        return None


def is_known_video(store, campaign_id, video_id):
    """Check if a video_id is already registered in the store for this campaign.

    Performs only a read-only SELECT; zero database mutations.
    """
    if not store:
        return False
    rows = store.rows(
        "SELECT id FROM vods WHERE campaign=? AND ("
        "source_key=? OR source_key LIKE ? OR "
        "json_extract(data, '$.provider_vod_id')=? OR "
        "json_extract(data, '$.url') LIKE ?)",
        (campaign_id, f"https://www.youtube.com/watch?v={video_id}", f"%{video_id}%", video_id, f"%{video_id}%")
    )
    return len(rows) > 0


def classify_discovery_item(item, campaign, is_known):
    """Assign status and human-readable reason to a discovered item.

    Statuses:
    - LIVE_NOW: Live stream currently active
    - UPCOMING: Live stream scheduled/upcoming
    - KNOWN: Video already exists in the database for this campaign
    - OUT_OF_PERIOD: Date is outside the campaign's allowed period
    - NEEDS_REVIEW: Missing date or campaign without defined min_date
    - NEW: Within allowed period, ready for operator to import
    """
    live_status = item.get("live_status")
    if live_status in ("is_live", "live") or item.get("is_live"):
        return "LIVE_NOW", "Transmissão ao vivo em andamento; não pode ser importada enquanto ativa."
    if live_status in ("is_upcoming", "upcoming") or item.get("is_upcoming"):
        return "UPCOMING", "Transmissão agendada; ainda não realizada."

    if is_known:
        return "KNOWN", "Vídeo já cadastrado nesta campanha."

    upload_date = item.get("upload_date")
    min_date = campaign.get("min_date")
    max_date = campaign.get("max_date")

    if min_date:
        if not upload_date:
            return "NEEDS_REVIEW", f"Data não confirmada na listagem; campanha requer conteúdo a partir de {min_date}."
        if upload_date < min_date:
            return "OUT_OF_PERIOD", f"Publicado em {upload_date}, anterior à data mínima da campanha ({min_date})."
        if max_date and upload_date > max_date:
            return "OUT_OF_PERIOD", f"Publicado em {upload_date}, posterior à data máxima da campanha ({max_date})."
        return "NEW", "Dentro do período da campanha; disponível para importação."
    else:
        if not upload_date:
            return "NEEDS_REVIEW", "Data não informada e campanha sem período definido; requer revisão humana."
        return "NEEDS_REVIEW", "Campanha sem data mínima definida; requer confirmação humana do período."


def normalize_entry(entry, source_type="channel"):
    """Normalize raw entry dictionary from yt-dlp to standard contract."""
    if not isinstance(entry, dict):
        return None
    video_id = entry.get("id")
    if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None

    was_live = entry.get("was_live")
    live_status = entry.get("live_status")
    if live_status in ("was_live", "post_live"):
        was_live = True
    elif live_status == "not_live":
        was_live = False

    raw_upload = entry.get("upload_date")
    norm_upload = parse_upload_date(raw_upload)

    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
    if not timestamp and norm_upload:
        try:
            timestamp = datetime.strptime(norm_upload, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
        except Exception:
            timestamp = None
    elif timestamp and not norm_upload:
        try:
            norm_upload = datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")
        except Exception:
            pass

    duration = entry.get("duration")

    return {
        "source_id": f"youtube:{video_id}",
        "platform": "YouTube",
        "source_type": source_type,
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "title": entry.get("title"),
        "channel_id": entry.get("channel_id") or entry.get("uploader_id"),
        "channel_name": entry.get("channel") or entry.get("uploader"),
        "channel_url": entry.get("channel_url") or entry.get("uploader_url"),
        "upload_date": norm_upload,
        "timestamp": timestamp,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "was_live": was_live,
        "live_status": live_status or ("is_live" if entry.get("is_live") else None),
        "playlist_id": entry.get("playlist_id"),
        "playlist_title": entry.get("playlist_title"),
        "playlist_position": entry.get("playlist_index"),
        "status": None,
        "status_reason": None,
    }


def discover_source(provider, campaign, url, limit=50, store=None, check=lambda: None):
    """Discover YouTube videos ephemerally for a campaign without persisting or downloading media.

    Returns:
        dict with campaign, source_url, limit, count, summary, items.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Limite de descoberta deve estar entre 1 e 100.")

    url = str(url).strip()
    source_type = "channel"
    is_single = False
    canonical_url = None

    # 1. Try single video URL first
    try:
        plat, norm = validate_url(url)
        if plat == "YouTube":
            is_single = True
            canonical_url = norm
            source_type = "video"
    except ValueError:
        pass

    # 2. If not single video, try channel or playlist
    if not is_single:
        try:
            canonical_url = youtube_source(url)
            if "/playlist" in canonical_url:
                source_type = "playlist"
            else:
                source_type = "channel"
        except ValueError as exc:
            raise ValueError(
                f"URL do YouTube não reconhecida: {url}. "
                "Informe um canal (@handle, /channel/, /c/), playlist ou vídeo."
            ) from exc

    raw_entries = []

    # 3. Execute metadata extraction without downloading media
    if is_single:
        cmd = [
            provider.python(), "-m", "yt_dlp", "--ignore-config", "--skip-download",
            "--dump-single-json", "--no-playlist", "--socket-timeout", "30", "--retries", "2",
            "--", canonical_url
        ]
        output = provider.execute(cmd, check=check, timeout=120)
        try:
            val = json.loads(output)
            if isinstance(val, dict):
                if isinstance(val.get("entries"), list):
                    raw_entries.extend(val["entries"])
                else:
                    raw_entries.append(val)
        except Exception as exc:
            raise ValueError("Falha ao processar metadados do vídeo.") from exc
    else:
        cmd = discovery_args(provider.python(), canonical_url, limit)
        output = provider.execute(cmd, check=check, timeout=120)
        try:
            data = json.loads(output)
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                raw_entries = data["entries"][:limit]
            else:
                raise ValueError("Formato de listagem retornado pelo yt-dlp é inválido.")
        except Exception as exc:
            raise ValueError("Falha ao listar conteúdos do canal/playlist.") from exc

    # 4. Normalize and deduplicate by video_id
    items = []
    seen = set()

    for raw in raw_entries:
        check()
        norm = normalize_entry(raw, source_type=source_type)
        if not norm:
            continue
        vid = norm["video_id"]
        if vid in seen:
            continue
        seen.add(vid)

        # Check if already known in database
        known = is_known_video(store, campaign["id"], vid)

        # Classify status
        status, reason = classify_discovery_item(norm, campaign, known)
        norm["status"] = status
        norm["status_reason"] = reason
        items.append(norm)

    # 5. Build summary
    summary = {
        "new": sum(1 for i in items if i["status"] == "NEW"),
        "known": sum(1 for i in items if i["status"] == "KNOWN"),
        "out_of_period": sum(1 for i in items if i["status"] == "OUT_OF_PERIOD"),
        "needs_review": sum(1 for i in items if i["status"] == "NEEDS_REVIEW"),
        "upcoming": sum(1 for i in items if i["status"] == "UPCOMING"),
        "live_now": sum(1 for i in items if i["status"] == "LIVE_NOW"),
    }

    return {
        "campaign": campaign["id"],
        "campaign_name": campaign.get("name", campaign["id"]),
        "source_url": canonical_url,
        "source_type": source_type,
        "limit": limit,
        "count": len(items),
        "summary": summary,
        "items": items,
    }
