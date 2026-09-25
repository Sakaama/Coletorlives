"""Public CLI adapters only; discovery and range transfer use installed tools."""
import json
import os
import re
from datetime import datetime, UTC
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from miner import media, performance
from miner.range_download import any_command
from miner.rules import validate_url
from miner.ytdlp_cli import discovery_args


def youtube_source(value):
    """Validate catalog URLs separately from single-video import URLs."""
    value = str(value).strip()
    if re.fullmatch(r"@?[A-Za-z0-9_.-]{1,80}", value):
        value = "https://www.youtube.com/" + ("channel/" + value if re.fullmatch(r"UC[A-Za-z0-9_-]{22}", value) else "@" + value.lstrip("@"))
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com")
            or parsed.username or parsed.password or parsed.port or parsed.fragment):
        raise ValueError("Informe uma URL HTTPS de canal ou playlist do YouTube.")
    if parsed.path.rstrip("/") == "/playlist":
        query = parse_qs(parsed.query)
        playlist = query.get("list", [""])[0]
        if set(query) != {"list"} or not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", playlist):
            raise ValueError("Playlist do YouTube inválida.")
        return "https://www.youtube.com/playlist?list=" + playlist
    if parsed.query or not re.fullmatch(r"/(?:@[\w.-]{1,80}|channel/UC[A-Za-z0-9_-]{22}|(?:c|user)/[\w.-]{1,80})(?:/(?:videos|streams|shorts))?/?", parsed.path):
        raise ValueError("Informe um canal ou playlist do YouTube; use a inclusão manual para links de vídeos.")
    path = parsed.path.rstrip("/")
    if path.rsplit("/", 1)[-1] not in ("videos", "streams", "shorts"):
        path += "/videos"
    return "https://www.youtube.com" + path


def youtube_row(value):
    video = value.get("id", "")
    if not isinstance(video, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("ID de vídeo inválido na listagem YouTube.")
    was_live = value.get("was_live")
    if value.get("live_status") in ("was_live", "post_live"):
        was_live = True
    elif value.get("live_status") == "not_live":
        was_live = False
    live_date = value.get("release_timestamp") if was_live is True else None
    stamp = live_date or value.get("timestamp")
    if not stamp and value.get("upload_date"):
        try:
            stamp = datetime.strptime(value["upload_date"], "%Y%m%d").replace(tzinfo=UTC).timestamp()
        except (TypeError, ValueError):
            pass
    return {"provider": "youtube", "kind": "vod", "id": video,
            "webUrl": "https://www.youtube.com/watch?v=" + video,
            "title": value.get("title"), "channel": value.get("channel"),
            "channel_id": value.get("channel_id"), "was_live": was_live,
            "date_kind": "live" if live_date else "upload", "startTime": stamp,
            "durationSec": value.get("duration"), "catalog_discovery": True}


class Cancelled(BaseException):
    pass


class QualityUnavailable(ValueError):
    pass


class Provider:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @performance.measure("remote_tool")
    def execute(self, args, check=lambda: None, progress=lambda *a: None, timeout=900):
        start = time.monotonic()
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(args, cwd=str(self.root), env=None, shell=False,
                                    stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                    creationflags=media.FLAGS)
            try:
                while True:
                    check()
                    try:
                        code = proc.wait(timeout=0.5)
                        break
                    except subprocess.TimeoutExpired:
                        progress(0, f"Ferramenta remota · {time.monotonic() - start:.0f}s")
                        if time.monotonic() - start > timeout:
                            raise ValueError("Tempo excedido na ferramenta remota.") from None
            finally:
                if proc.poll() is None:
                    if os.name == "nt":
                        # Only this tool's process tree (including its FFmpeg child).
                        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=media.FLAGS, check=False)
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait()
            errors.seek(0, 2)
            errors.seek(max(0, errors.tell() - 4000))
            error = errors.read().decode("utf-8", errors="replace")
            if code:
                raise ValueError(error[-2000:] or f"Ferramenta retornou código {code}.")
            output.seek(0)
            return output.read().decode("utf-8", errors="replace")

    def python(self):
        return str(self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))

    def discover(self, provider, channel, limit=100, check=lambda: None):
        if provider == "YouTube":
            return self.discover_youtube(channel, limit, check)
        if provider not in ("Kick", "Twitch"):
            raise ValueError("Descoberta automática indisponível nesta fonte. Inclua URLs manualmente.")
        output = self.execute([*any_command(), provider.lower(), channel, "--list", "--limit", str(limit), "--json"], check, timeout=120)
        rows = json.loads(output)
        if not isinstance(rows, list):
            raise ValueError("Listagem remota inválida; use inclusão manual de URL.")
        return rows

    def discover_youtube(self, channel, limit=100, check=lambda: None):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limite de descoberta deve estar entre 1 e 100.")
        source = youtube_source(channel)
        check()
        data = json.loads(self.execute(discovery_args(self.python(), source, limit), check, timeout=120))
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise ValueError("Listagem YouTube inválida.")
        rows, seen = [], set()
        for entry in data["entries"][:limit]:
            check()
            if not isinstance(entry, dict) or entry.get("is_live") or entry.get("live_status") in ("is_live", "is_upcoming"):
                continue
            if entry.get("availability") in ("private", "premium_only", "subscriber_only", "needs_auth"):
                continue
            try:
                row = youtube_row(entry)
            except ValueError:
                continue
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            if not row["startTime"]:
                try:
                    row = self.metadata(row["webUrl"], check=check)
                except ValueError:
                    pass  # Undated rows are reported, never assigned an invented date.
            rows.append(row)
        return rows

    def metadata(self, url, quality="worst", check=lambda: None):
        provider, url = validate_url(url)
        if provider in ("Kick", "Twitch"):
            return json.loads(self.execute([*any_command(), url, "--quality", quality, "--json", "--yes"], check, timeout=120))
        value = json.loads(self.execute([self.python(), "-m", "yt_dlp", "--ignore-config", "--skip-download", "--dump-single-json", "--no-playlist", "--socket-timeout", "30", "--retries", "2", "--", url], check, timeout=120))
        if not isinstance(value, dict):
            raise ValueError("Metadados YouTube inválidos.")
        if value.get("is_live") or value.get("live_status") in ("is_live", "is_upcoming"):
            raise ValueError("A transmissão está ao vivo ou agendada.")
        return youtube_row(value)

    def download(self, url, target, start, end, quality="analysis", check=lambda: None, progress=lambda *a: None):
        if not 0 <= start < end or end - start > 900:
            raise ValueError("Range remoto deve ser positivo e ter no máximo 15 minutos.")
        provider, canonical = validate_url(url)
        source = canonical
        if provider in ("Kick", "Twitch"):
            try:
                info = self.metadata(canonical, "1080p60" if quality == "1080p60" else "best" if quality == "best" else "worst", check)
                if quality == "preview":
                    variants = [q for q in info.get("availableQualities", []) if q.startswith(("360p", "480p"))]
                    if variants:
                        info = self.metadata(canonical, sorted(variants)[0], check)
                    if not info.get("selectedQuality", "").startswith(("160p", "240p", "360p", "480p")):
                        raise ValueError("Fonte sem variante leve para Preview; use arquivo local.")
            except ValueError as exc:
                if quality == "1080p60" and any(word in str(exc).lower() for word in ("quality", "variant", "1080")):
                    raise QualityUnavailable("1080p60 indisponível; você pode tentar a melhor qualidade disponível.") from exc
                raise
            source = info.get("sourceUrl")
            if not source or urlparse(source).scheme != "https":
                raise ValueError("A ferramenta não forneceu mídia pública utilizável. Use arquivo local.")
        target = Path(target)
        # Public any-dl JSON resolves the source; yt-dlp performs the bounded accurate seek.
        # Re-encoding at the cut avoids treating any-dl keyframe offsets as exact timestamps.
        fmt = "bv[height=1080][fps>=59]+ba/b[height=1080][fps>=59]" if quality == "1080p60" else "bv*+ba/b" if quality == "best" else "worst"
        if quality == "preview":
            fmt = "b[height<=480]/bv[height<=480]+ba"
        if provider in ("Kick", "Twitch"):
            fmt = "best"
        args = [self.python(), "-m", "yt_dlp", "--no-playlist", "--no-overwrites", "--no-part",
                "--format", fmt, "--download-sections", f"*{start:.3f}-{end:.3f}",
                "--force-keyframes-at-cuts", "--merge-output-format", "mp4", "--remux-video", "mp4",
                "--output", str(target), "--socket-timeout", "30", "--retries", "2",
                "--js-runtimes", "node", "--", source]
        self.execute(args, check, progress)
        actual = media.probe(target)
        if abs(actual["duration"] - (end - start)) > 1:
            raise ValueError("Duração do range diverge da solicitada; não será usado como timestamp preciso.")
        if quality == "1080p60" and (actual["height"] != 1080 or actual.get("fps", 0) < 59):
            raise QualityUnavailable("1080p60 não confirmado. Tente a melhor qualidade disponível.")
        return {"requested_start": start, "requested_end": end, "obtained_duration": actual["duration"],
                "obtained_start": None, "obtained_end": None, "seek": "yt-dlp force-keyframes-at-cuts",
                "note": "Origem temporal calculada pelo seek da ferramenta; início absoluto não medido independentemente.",
                "media": actual, "quality": quality}
