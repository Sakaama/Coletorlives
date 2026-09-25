import json
import math
import os
import subprocess
import unicodedata
import wave
from pathlib import Path

import numpy as np

from miner.media import FLAGS, ffmpeg
from miner import performance


def save_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def energy(audio, cache, progress=None):
    if Path(cache).exists():
        return json.loads(Path(cache).read_text(encoding="utf-8"))
    values = []
    # 1 second per read, independent of VOD length. Input is mono 16-bit PCM.
    with wave.open(str(audio), "rb") as wav:
        rate, total = wav.getframerate(), wav.getnframes()
        while block := wav.readframes(rate):
            samples = np.frombuffer(block, dtype="<i2").astype(np.float32) / 32768
            values.append(float(np.sqrt(np.mean(samples * samples))))
            if progress and len(values) % 30 == 0:
                progress(min(99, len(values) * rate / max(total, 1) * 100))
    save_json(cache, values)
    return values


def hardware():
    gpu = None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=FLAGS,
        )
        if r.returncode == 0:
            gpu = r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "cpu_threads": os.cpu_count(),
        "gpu": gpu,
        "recommended": "cpu",
        "note": "CPU int8 é o padrão. CUDA requer cuBLAS/cuDNN compatíveis; falhas usam CPU.",
    }


def transcribe(audio, directory, models, duration, model_name="base", device="cpu", progress=None):
    from faster_whisper import WhisperModel

    directory = Path(directory) / model_name
    directory.mkdir(parents=True, exist_ok=True)
    complete = directory / "transcript.json"
    if complete.exists():
        return json.loads(complete.read_text(encoding="utf-8"))
    if model_name not in ("tiny", "base", "small") or device not in ("cpu", "cuda"):
        raise ValueError("Modelo ou dispositivo inválido.")
    if progress:
        progress(0, "Carregando modelo local (primeiro uso baixa o modelo).")
    model = None
    segments = []
    for index, offset in enumerate(range(0, math.ceil(duration), 300)):
        checkpoint = directory / f"chunk_{index:05}.json"
        if checkpoint.exists():
            segments.extend(json.loads(checkpoint.read_text(encoding="utf-8")))
            continue
        chunk = directory / f"chunk_{index:05}.wav"
        ffmpeg(
            [
                "-ss",
                offset,
                "-i",
                audio,
                "-t",
                min(300, duration - offset),
                "-ac",
                1,
                "-ar",
                16000,
                "-c:a",
                "pcm_s16le",
            ],
            chunk,
        )
        if model is None:
            try:
                model = performance.model((WhisperModel, model_name, device, str(models)), lambda device=device: WhisperModel(
                    model_name,
                    device=device,
                    compute_type="int8" if device == "cpu" else "int8_float16",
                    cpu_threads=min(8, os.cpu_count() or 4),
                    download_root=str(models),
                ))
            except Exception:
                if device != "cuda":
                    raise
                device = "cpu"
                if progress:
                    progress(offset / duration * 100, "GPU indisponível; transcrevendo em CPU.")
                model = performance.model((WhisperModel, model_name, "cpu", str(models)), lambda: WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(models)))
        try:
            iterator, _ = model.transcribe(str(chunk), language="pt", vad_filter=True, beam_size=3)
            part = []
            for s in iterator:
                part.append(
                    {
                        "start": round(offset + s.start, 3),
                        "end": round(min(duration, offset + s.end), 3),
                        "text": s.text.strip(),
                    }
                )
                if progress:
                    progress(min(99, (offset + s.end) / duration * 100), "Transcrevendo com timestamps…")
        except Exception:
            if device == "cuda":
                # Restart in CPU; existing completed checkpoints remain usable.
                del model
                return transcribe(audio, directory.parent, models, duration, model_name, "cpu", progress)
            raise
        save_json(checkpoint, part)
        segments.extend(part)
    save_json(complete, segments)
    (directory / "transcript.txt").write_text(
        "\n".join(f"[{timestamp(s['start'])} → {timestamp(s['end'])}] {s['text']}" for s in segments),
        encoding="utf-8",
    )
    return segments


def timestamp(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


# The VOD detector is isolated from transcription and media processing.
from miner.vod_mining import detect  # noqa: E402,F401
