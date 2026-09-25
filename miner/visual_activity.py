"""Sparse visual change, not image understanding or a candidate detector."""

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from miner import media
from miner.analysis import save_json

VERSION = "visual-pairs-1"
INTERVAL = 20
WIDTH, HEIGHT = 160, 90
MAX_BOOST = 8


def frame(source, timestamp):
    # Input seeking decodes only around the sample, not the entire VOD.
    result = subprocess.run(
        [media.binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
         "-threads", "1", "-ss", str(timestamp), "-i", str(source),
         "-map", "0:v:0", "-an", "-sn", "-frames:v", "1",
         "-vf", f"scale={WIDTH}:{HEIGHT}", "-pix_fmt", "gray",
         "-threads", "1", "-f", "rawvideo", "pipe:1"],
        capture_output=True, check=True, timeout=30, creationflags=media.FLAGS,
    )
    if len(result.stdout) != WIDTH * HEIGHT:
        raise ValueError("Amostra visual incompleta.")
    return np.frombuffer(result.stdout, dtype=np.uint8)


def change_score(before, after):
    delta = np.abs(before.astype(np.float32) - after.astype(np.float32))
    # Require both magnitude and changed area; small webcam motion has less weight.
    strength = min(1.0, float(delta.mean()) / 32)
    area = min(1.0, float((delta > 12).mean()) / 0.6)
    return round(100 * (0.6 * strength + 0.4 * area), 1)


def sample(source, duration, cache, progress=None, offset=0):
    source, cache = Path(source), Path(cache)
    stat = source.stat()
    signature = dict(version=VERSION, source=str(source.resolve()), size=stat.st_size,
                     mtime_ns=stat.st_mtime_ns, duration=duration, interval=INTERVAL,
                     width=WIDTH, height=HEIGHT, offset=offset)
    if cache.exists():
        try:
            saved = json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("signature") == signature and isinstance(saved.get("samples"), list):
                return saved["samples"]
        except (ValueError, OSError):
            pass
    samples = []
    count = math.ceil(duration / INTERVAL)
    for i in range(count):
        start, end = i * INTERVAL, min((i + 1) * INTERVAL, duration)
        if end - start < 0.2:
            continue
        t = offset + (start + end) / 2
        other = min(t + 1, offset + end - 0.05)
        score = change_score(frame(source, t), frame(source, other))
        samples.append({"time": t, "score": score})
        if progress:
            progress(100 * (i + 1) / count)
    # Write only complete measurements. A failed run must not cache false inactivity.
    save_json(cache, {"signature": signature, "samples": samples})
    return samples


def rank(candidates, samples):
    ranked = []
    for candidate in candidates:
        values = [s["score"] for s in samples if candidate["start"] <= s["time"] < candidate["end"]]
        visual = round(float(np.mean(values)), 1) if values else None
        level = None if visual is None else "HIGH" if visual >= 60 else "MEDIUM" if visual >= 25 else "LOW"
        editorial = candidate.get("editorial_score", candidate["score"])
        # Audio-only exploratory candidates stay weak even with a moving image.
        boost = round(MAX_BOOST * visual / 100) if visual is not None and editorial > 15 else 0
        ranked.append({**candidate, "editorial_score": editorial,
                       "score": min(100, editorial + boost), "visual_boost": boost,
                       "visual_activity_score": visual, "visual_activity_level": level,
                       "visual_sample_count": len(values), "visual_version": VERSION})
    return sorted(ranked, key=lambda c: (-c["score"], c["start"]))
