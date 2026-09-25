"""Small real inference test, using a locally synthesized fixture."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner.analysis import transcribe  # noqa: E402
from miner.media import probe  # noqa: E402

if __name__ == "__main__":
    video = ROOT / "test-results" / "demo.mp4"
    result = transcribe(
        ROOT / "test-results/speech-en.wav",
        ROOT / "test-results/transcription",
        ROOT / "models",
        probe(video)["duration"],
        model_name="base",
        device="cpu",
        progress=lambda p, m: print(f"{p:.1f}% {m}", flush=True),
    )
    assert result and all(s["end"] > s["start"] >= 0 for s in result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
