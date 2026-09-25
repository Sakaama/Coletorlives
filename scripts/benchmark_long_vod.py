"""Comparable cold/warm pipelines on a local excerpt; no operational database writes."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner import analysis, long_vod, media, visual_activity  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--output", type=Path, default=ROOT / "test-results/v1-benchmark")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use --output com um diretório novo para comparar execução fria e cache sem misturá-los.")
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output / "sample.mp4"
    media.ffmpeg(["-ss", 0, "-i", args.source, "-t", args.seconds, "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy"], source)
    info = media.probe(source)
    results = {"source": args.source, "sample": str(source), "duration": info["duration"], "device": "cpu", "runs": []}
    for pipeline in ("previous", "long"):
        for pass_number in (1, 2):
            start = time.perf_counter()
            folder = args.output / pipeline
            folder.mkdir(exist_ok=True)
            if pipeline == "previous":
                metrics = {}
                def measure(label, fn, metrics=metrics):
                    begin = time.perf_counter()
                    value = fn()
                    metrics[label] = time.perf_counter() - begin
                    return value
                audio = folder / "audio.wav"
                measure("audio", lambda audio=audio: media.extract_audio(source, audio, info["duration"]))
                energy = measure("fast_scan", lambda audio=audio, folder=folder: analysis.energy(audio, folder / "energy.json"))
                words = measure("transcription", lambda audio=audio, folder=folder: analysis.transcribe(audio, folder, ROOT / "models", info["duration"]))
                found = measure("deep_analysis", lambda words=words, energy=energy: analysis.detect(words, energy, info["duration"]))
                samples = measure("visual", lambda folder=folder: visual_activity.sample(source, info["duration"], folder / "visual.json"))
                found = measure("ranking", lambda found=found, samples=samples: visual_activity.rank(found, samples))
                metrics.update(regions=1, deep_regions=1, deep_seconds=info["duration"], candidates=len(found))
            else:
                found, warnings, metrics, _ = long_vod.run(source, folder, ROOT / "models", info,
                                                         {"model": "base", "device": "cpu"}, lambda p, m: print(m, flush=True))
                metrics["warnings"] = warnings
            metrics["total"] = time.perf_counter() - start
            results["runs"].append({"pipeline": pipeline, "pass": pass_number, "metrics": metrics,
                                    "candidates": found})
            analysis.save_json(args.output / "report.json", results)
            print(json.dumps(results["runs"][-1]["metrics"]), flush=True)
