"""Run each device in a separate process; native CUDA failures cannot stop the app."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner import analysis, media  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "cuda"])
    parser.add_argument("--audio", default=str(ROOT / "test-results/speech-en.wav"))
    args = parser.parse_args()
    if args.device:
        from faster_whisper import WhisperModel
        start = time.perf_counter()
        try:
            model = WhisperModel("base", device=args.device,
                                 compute_type="int8" if args.device == "cpu" else "int8_float16",
                                 cpu_threads=min(8, os.cpu_count() or 4), download_root=str(ROOT / "models"),
                                 local_files_only=True)
            loaded = time.perf_counter()
            segments, _ = model.transcribe(args.audio, language="pt", vad_filter=True, beam_size=3)
            rows = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
            print(json.dumps({"device": args.device, "load_seconds": loaded - start,
                              "inference_seconds": time.perf_counter() - loaded, "segments": len(rows)}))
        except Exception as exc:
            print(json.dumps({"device": args.device, "error": str(exc), "seconds": time.perf_counter() - start}))
    else:
        results = []
        for device in ("cpu", "cuda"):
            result = subprocess.run([sys.executable, __file__, "--device", device, "--audio", args.audio],
                                    capture_output=True, text=True, timeout=180, creationflags=media.FLAGS)
            results.append({"device": device, "exit_code": result.returncode,
                            "output": result.stdout.strip(), "stderr": result.stderr[-1500:]})
        analysis.save_json(ROOT / "test-results/v1-gpu.json", {"hardware": analysis.hardware(), "audio": args.audio, "runs": results})
        print(json.dumps(results, indent=2))
