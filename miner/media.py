import json
import logging
import os
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

LOG = logging.getLogger(__name__)
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def binary(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f"{name} não encontrado. Instale FFmpeg e adicione sua pasta bin ao PATH.")
    return found


def probe(path):
    process = subprocess.run(
        [binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        creationflags=FLAGS,
    )
    if process.returncode:
        raise ValueError("Não foi possível ler o vídeo: " + process.stderr[-1500:])
    data = json.loads(process.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("O arquivo precisa conter uma faixa de vídeo.")
    return {
        "duration": float(data["format"].get("duration", video.get("duration", 0))),
        "width": video["width"],
        "height": video["height"],
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
        "video_codec": video["codec_name"],
        "fps": float(Fraction(video.get("avg_frame_rate", "0/1"))) if video.get("avg_frame_rate") not in (None, "0/0") else 0,
    }


def ffmpeg(args, target, duration=0, progress=None):
    """Stream progress; publish only complete files, never replace an existing result."""
    target = Path(target)
    if target.exists():
        return target
    temporary = target.with_name(target.stem + ".partial-" + uuid.uuid4().hex[:8] + target.suffix)
    command = [
        binary("ffmpeg"),
        "-hide_banner",
        "-nostdin",
        "-n",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        *map(str, args),
        str(temporary),
    ]
    LOG.info("FFmpeg: %s", subprocess.list2cmdline(command))
    # Error output goes to disk, so long videos cannot fill a pipe or RAM.
    error_path = temporary.with_suffix(temporary.suffix + ".log")
    with error_path.open("w+", encoding="utf-8") as errors:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=FLAGS,
        )
        for line in proc.stdout:
            if progress and line.startswith("out_time_us="):
                try:
                    progress(min(99, float(line.split("=")[1]) / 1e6 / max(duration, 1) * 100))
                except ValueError:
                    pass
        proc.stdout.close()
        code = proc.wait()
        if code:
            errors.seek(0)
            detail = errors.read()[-2500:]
            LOG.error("FFmpeg falhou: %s", detail)
            raise ValueError("FFmpeg não concluiu o processamento. " + detail)
    temporary.rename(target)
    return target


def extract_audio(source, target, duration, progress=None):
    return ffmpeg(
        ["-i", source, "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le", "-rf64", "auto"],
        target,
        duration,
        progress,
    )


def clip(source, target, start, end, preview=False, progress=None):
    # Re-encode for exact boundaries, preserving source resolution/fps for RAW.
    args = [
        "-ss",
        start,
        "-i",
        source,
        "-t",
        end - start,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-threads",
        4,
        "-preset",
        "veryfast" if preview else "fast",
        "-crf",
        27 if preview else 16,
    ]
    if preview:
        args += ["-vf", "scale=640:-2,setsar=1"]
    args += [
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k" if preview else "320k",
        "-movflags",
        "+faststart",
    ]
    return ffmpeg(args, target, end - start, progress)


def frame(source, target, timestamp=0):
    return ffmpeg(["-ss", timestamp, "-i", source, "-frames:v", 1, "-update", 1], target)


def validate_rect(rect, width, height):
    try:
        x, y, w, h = (int(rect[k]) for k in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError):
        raise ValueError("Informe X, Y, largura e altura da região.") from None
    if x < 0 or y < 0 or w < 2 or h < 2 or x + w > width or y + h > height:
        raise ValueError("A região precisa ficar dentro do quadro original e ter pelo menos 2×2 pixels.")
    return {"x": x, "y": y, "width": w, "height": h}


def prep(source, target, camera, content, preset, duration, progress=None):
    ch, band = int(preset["camera_height"]), int(preset["band_height"])
    bottom = 1920 - ch - band
    if ch < 100 or band < 60 or bottom < 200 or any(v % 2 for v in (ch, band, bottom)):
        raise ValueError("Preset vertical inválido: use alturas pares que somem 1920.")

    def crop(r):
        return f"crop={r['width']}:{r['height']}:{r['x']}:{r['y']}"

    filters = (
        f"[0:v]split=2[cam][main];[cam]{crop(camera)},scale=1080:{ch}:"
        f"force_original_aspect_ratio=increase,crop=1080:{ch},setsar=1[top];"
        f"[main]{crop(content)},scale=1080:{bottom}:force_original_aspect_ratio=decrease,"
        f"pad=1080:{bottom}:(ow-iw)/2:(oh-ih)/2:black,setsar=1[bottom];"
        f"[top]pad=1080:{ch + band}:0:0:color=0x151823[head];[head][bottom]vstack=inputs=2[base]"
    )
    args = ["-i", source]
    asset = preset.get("asset")
    if asset:
        if not Path(asset).is_file():
            raise ValueError("Asset do lower não encontrado; confira a configuração da campanha.")
        args += ["-i", asset]
        filters += (
            f";[1:v]scale=1080:{band}:force_original_aspect_ratio=decrease[lower];"
            f"[base][lower]overlay=(W-w)/2:{ch}:eof_action=repeat[out]"
        )
    else:
        # Text is supplied through a sidecar to avoid interpreting filter syntax.
        text_path = Path(target).with_suffix(".txt")
        text_path.write_text(preset["text"], encoding="utf-8")
        escaped = str(text_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        x, y = int(preset["text_x"]), int(preset["text_y"])
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
        font_option = ""
        if font.is_file():
            font_path = font.as_posix().replace(":", "\\:")
            font_option = f"fontfile='{font_path}':"
        filters += (
            f";[base]drawtext={font_option}textfile='{escaped}':fontcolor=white:fontsize=34:"
            f"x={x}:y={y}:fix_bounds=1[out]"
        )
    args += [
        "-filter_complex",
        filters,
        "-filter_complex_threads",
        2,
        "-map",
        "[out]",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-threads",
        4,
        "-preset",
        "veryfast",
        "-crf",
        20,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
    ]
    return ffmpeg(args, target, duration, progress)
