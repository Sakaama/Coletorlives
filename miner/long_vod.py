"""Incremental cheap scan and selective transcription on an absolute VOD timeline."""
import hashlib
import json
import math
import time
import uuid
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from miner import analysis, media, visual_activity, performance

VERSION = "long-vod-1"
CONFIG = {"chunk": 600, "cell": 60, "context": 45, "deep_chunk": 300,
          "visual_threshold": 60, "visual_variation": 20, "audio_ratio": 2.5, "audio_floor": 0.015,
          "probe_every": 300, "probe_seconds": 30}


def chunks(duration, size=600):
    result = []
    for s in range(0, math.ceil(duration), size):
        end = min(s + size, duration)
        if end - s < 0.1 and result:
            result[-1] = (result[-1][0], end)
        else:
            result.append((s, end))
    return result


def fingerprint(source, duration):
    p = Path(source).resolve()
    st = p.stat()
    payload = [str(p), st.st_size, st.st_mtime_ns, duration, VERSION, CONFIG["chunk"],
               visual_activity.VERSION, visual_activity.INTERVAL, visual_activity.WIDTH, visual_activity.HEIGHT]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def absolute(segments, offset):
    return [{**s, "start": round(s["start"] + offset, 3), "end": round(s["end"] + offset, 3)} for s in segments]


def merge_regions(regions, duration):
    result = []
    for start, end in sorted(regions):
        start, end = max(0, start), min(duration, end)
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def promising(energies, samples, duration):
    regions = []
    for start, end in chunks(duration, CONFIG["cell"]):
        values = np.asarray(energies[int(start):math.ceil(end)])
        if not len(values):
            continue
        audible = np.count_nonzero(values > 0.003) >= min(5, len(values))
        baseline = max(0.003, float(np.median(values)))
        varied = np.count_nonzero(values > max(CONFIG["audio_floor"], baseline * CONFIG["audio_ratio"])) >= 3
        activity = [s["score"] for s in samples if start <= s["time"] < end]
        # Uniform motion is not an event: require a change in activity as well.
        visual = (len(activity) >= 2 and max(activity) >= CONFIG["visual_threshold"]
                  and max(activity) - min(activity) >= CONFIG["visual_variation"])
        if audible and (visual or varied):
            regions.append((start - CONFIG["context"], end + CONFIG["context"]))
    return merge_regions(regions, duration)


def dedup_segments(segments):
    result = []
    for row in sorted(segments, key=lambda s: (s["start"], s["end"])):
        text = analysis.normalize(row["text"])
        duplicate = False
        for old in reversed(result[-12:]):
            overlap = min(old["end"], row["end"]) - max(old["start"], row["start"])
            shorter = min(old["end"] - old["start"], row["end"] - row["start"])
            if overlap > 0.6 * max(0.01, shorter) and SequenceMatcher(None, analysis.normalize(old["text"]), text).ratio() > 0.85:
                duplicate = True
                break
        if not duplicate:
            result.append(row)
    return result


def region_audio(base, source, target, start, end, duration):
    """Slice cached PCM chunks, avoiding another decode of the proxy for each region."""
    if target.exists():
        return target
    parts = [(i, a, b) for i, (a, b) in enumerate(chunks(duration, CONFIG["chunk"])) if a < end and b > start]
    files = [Path(base) / f"scan_{i:05}" / "audio.wav" for i, _, _ in parts]
    if not all(p.exists() for p in files):
        return media.ffmpeg(["-ss", start, "-i", source, "-t", end - start,
                             "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le"], target, end - start)
    temporary = target.with_name(target.stem + ".partial-" + uuid.uuid4().hex[:8] + ".wav")
    with wave.open(str(temporary), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        for file, (_, a, b) in zip(files, parts, strict=True):
            with wave.open(str(file), "rb") as audio:
                if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                    raise ValueError("Checkpoint de áudio incompatível.")
                position = round((max(start, a) - a) * 16000)
                remaining = min(round((min(end, b) - max(start, a)) * 16000), audio.getnframes() - position)
                audio.setpos(position)
                while remaining > 0:
                    frames = min(remaining, 480000)
                    output.writeframesraw(audio.readframes(frames))
                    remaining -= frames
    temporary.replace(target)
    return target


@performance.session()
def run(source, directory, models, info, options, progress, adapter=None):
    started = time.perf_counter()
    duration = info["duration"]
    base = Path(directory) / ("remote" if adapter else "long") / (adapter.key() if adapter else fingerprint(source, duration))
    base.mkdir(parents=True, exist_ok=True)
    model, device = options.get("model", "base"), options.get("device", "cpu")
    metrics = {name: 0.0 for name in ("audio", "visual", "fast_scan", "transcription", "deep_analysis", "deduplication", "ranking")}
    metrics.update(chunks=0, chunks_cached=0, regions=0, deep_regions=0, transcription_cached=0, device_requested=device)
    warnings, errors, energies, samples = [], [], [], []
    manifest = base / "checkpoint.json"
    last_progress = 0

    def report(value, message):
        nonlocal last_progress
        if adapter:
            adapter.check()
        last_progress = max(last_progress, value)
        progress(last_progress, f"{message} · decorrido {analysis.timestamp(time.perf_counter() - started)} · checkpoints em disco")

    def timed(name, fn):
        begin = time.perf_counter()
        try:
            with performance.measure(name):
                return fn()
        finally:
            metrics[name] = metrics.get(name, 0) + time.perf_counter() - begin

    def checkpoint(stage):
        analysis.save_json(manifest, {"version": VERSION, "duration": duration, "source": str(source),
                                     "stage": stage, "config": CONFIG, "errors": errors, "metrics": metrics})

    parts = adapter.parts(duration) if adapter else chunks(duration, CONFIG["chunk"])
    if adapter:
        energies = [0.0] * math.ceil(duration)
    for index, (start, end) in enumerate(parts):
        folder = base / f"scan_{index:05}"
        folder.mkdir(exist_ok=True)
        complete = folder / "complete.json"
        report(index / len(parts) * 45, f"FAST SCAN · chunk {index + 1}/{len(parts)}")
        try:
            if complete.exists():
                data = json.loads(complete.read_text(encoding="utf-8"))
                metrics["chunks_cached"] += 1
            else:
                if adapter:
                    data = adapter.scan(start, end, folder, lambda n, index=index: report(index / len(parts) * 45, "FAST SCAN remoto"))
                    analysis.save_json(complete, data)
                else:
                    audio = folder / "audio.wav"
                    if info["has_audio"]:
                        timed("audio", lambda start=start, end=end, audio=audio, index=index: media.ffmpeg(
                            ["-ss", start, "-i", source, "-t", end - start, "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le"],
                            audio, end - start, lambda n, index=index: report((index + n / 100) / len(parts) * 45, f"ÁUDIO · chunk {index + 1}/{len(parts)}")))
                        energy = timed("fast_scan", lambda audio=audio, folder=folder: analysis.energy(audio, folder / "energy.json"))
                    else:
                        energy = [0.0] * math.ceil(end - start)
                    # Existing sampler/cache, scoped to a chunk for restart durability.
                    visual_ok = True
                    try:
                        visual = timed("visual", lambda start=start, end=end, folder=folder, index=index: visual_activity.sample(
                            source, end - start, folder / "visual.json",
                            lambda n: report((index + n / 100) / len(parts) * 45, f"VISUAL · chunk {index + 1}/{len(parts)}"), offset=start))
                    except Exception as exc:
                        visual_ok, visual = False, []
                        errors.append({"stage": "visual", "start": start, "end": end, "error": str(exc)[-500:]})
                    data = {"energy": energy, "visual": visual}
                    if visual_ok:
                        analysis.save_json(complete, data)
            if adapter:
                values = data["energy"][:math.ceil(end - start)]
                energies[int(start):int(start) + len(values)] = values
                adapter.completed(folder, complete)
            else:
                energies.extend(data["energy"][:math.ceil(end - start)])
            samples.extend(data["visual"])
            metrics["chunks"] += 1
        except Exception as exc:
            errors.append({"stage": "scan", "start": start, "end": end, "error": str(exc)[-500:]})
            if not adapter:
                energies.extend([0.0] * math.ceil(end - start))
        checkpoint("fast_scan")
        if adapter and errors:
            adapter.failed(manifest)

    regions = []

    def transcribe(start, end, label):
        folder = base / f"speech_{start:.3f}_{end:.3f}"
        folder.mkdir(exist_ok=True)
        audio = folder / "audio.wav"
        if adapter:
            if not (folder / model / "transcript.json").exists():
                audio = timed("audio", lambda: adapter.audio(start, end, folder))
        else:
            timed("audio", lambda: region_audio(base, source, audio, start, end, duration))
        if (folder / model / "transcript.json").exists():
            metrics["transcription_cached"] += 1
        words = absolute(timed("transcription", lambda: analysis.transcribe(
            audio, folder, models, end - start, model, device,
            lambda n, msg: report(50, f"{label} · {n:.0f}% · {msg}"))), start)
        if adapter:
            analysis.save_json(folder / model / "absolute.json", {"range_start": start, "range_end": end, "segments": words})
            adapter.completed(folder, folder / model / "transcript.json")
        return words

    plan_key = hashlib.sha256(json.dumps([CONFIG, model, options.get("transcribe", True)], sort_keys=True).encode()).hexdigest()[:16]
    plan = base / f"plan_{plan_key}.json"
    if plan.exists() and not errors:
        regions = json.loads(plan.read_text(encoding="utf-8"))
        metrics["fast_scan_cached"] = True
    else:
        regions = timed("fast_scan", lambda: promising(energies, samples, duration))
        if adapter:
            # Sparse noise/motion without sustained audible context is not a deep-analysis lead.
            regions = [r for r in regions if sum(e > 0.003 for e in energies[int(r[0]):math.ceil(r[1])]) / max(1, r[1]-r[0]) >= .3]
        if options.get("transcribe", True) and info["has_audio"]:
            # Small speech probes preserve a route for exceptional static talking.
            probes = chunks(duration, CONFIG["probe_every"])
            for index, (start, end) in enumerate(probes):
                if any(a <= start and end <= b for a, b in regions):
                    continue
                stop = min(end, start + CONFIG["probe_seconds"])
                if not any(e > 0.003 for e in energies[int(start):math.ceil(stop)]):
                    continue
                report(46, f"SONDAGEM DE FALA · {index + 1}/{len(probes)}")
                try:
                    words = timed("speech_probe", lambda start=start, stop=stop: transcribe(start, stop, "SONDAGEM DE FALA"))
                    from miner.editorial import relations
                    if analysis.detect(words, energies, duration, mode="agressivo") or relations(words, {"start": start, "end": stop}):
                        regions.append([max(0, start - 60), min(duration, stop + 120)])
                except Exception as exc:
                    errors.append({"stage": "probe", "start": start, "end": stop, "error": str(exc)[-500:]})
                checkpoint("speech_probes")
                if adapter and errors:
                    adapter.failed(manifest)
        regions = merge_regions(regions, duration)
        if not errors:
            analysis.save_json(plan, regions)
    metrics["regions"] = len(regions)
    units = [(a + start, a + end) for a, b in regions for start, end in chunks(b - a, CONFIG["deep_chunk"])]
    segments = []
    for index, (core_start, core_end) in enumerate(units):
        start, end = max(0, core_start - CONFIG["context"]), min(duration, core_end + CONFIG["context"])
        report(50 + index / max(1, len(units)) * 40, f"ANÁLISE PROFUNDA · região {index + 1}/{len(units)}")
        try:
            if options.get("transcribe", True) and info["has_audio"]:
                words = transcribe(start, end, f"ANÁLISE PROFUNDA · região {index + 1}/{len(units)}")
                segments.extend(s for s in words if core_start <= (s["start"] + s["end"]) / 2 < core_end)
            metrics["deep_regions"] += 1
        except Exception as exc:
            errors.append({"stage": "deep", "start": start, "end": end, "error": str(exc)[-500:]})
        checkpoint("deep_analysis")
        if adapter and errors:
            adapter.failed(manifest)
    segments = timed("deduplication", lambda: dedup_segments(segments))
    # A single detector call over all absolute segments performs global clustering.
    found = timed("deep_analysis", lambda: analysis.detect(segments, energies, duration, mode=options.get("mining_mode", "equilibrado")))
    found = timed("ranking", lambda: visual_activity.rank(found, samples))
    if adapter:
        for c in found:
            c["analysis_regions"] = [[a, b] for a, b in regions if a < c["end"] and b > c["start"]]
            c["type"] = "VISUAL" if c.get("visual_activity_level") in ("HIGH", "MEDIUM") else "TALKING"
    metrics.update(stage_timings=performance.timings(), total=time.perf_counter() - started, candidates=len(found),
                   deep_seconds=sum(b - a for a, b in regions), duration=duration)
    if errors:
        warnings.append(f"Análise parcial: {len(errors)} região(ões)/etapa(s) incompleta(s). Reanalise para tentar novamente; detalhes no checkpoint.")
    if not options.get("transcribe", True):
        warnings.append("Análise sem transcrição, conforme selecionado.")
    analysis.save_json(base / "result.json", {"regions": regions, "candidates": found, "metrics": metrics, "errors": errors})
    checkpoint("partial" if errors else "complete")
    return found, warnings, metrics, bool(segments)
