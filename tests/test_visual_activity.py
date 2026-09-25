import subprocess

import numpy as np
import pytest

from miner import media, visual_activity as visual
from miner.vod_mining import MODES, detect


def candidate(start, score=70):
    return {"start": start, "end": start + 30, "score": score, "reason": "hook; reação"}


def test_change_requires_area_and_magnitude():
    dark = np.zeros(14400, dtype=np.uint8)
    assert visual.change_score(dark, dark) == 0
    assert visual.change_score(dark, dark + 100) == 100
    webcam = dark.copy()
    webcam[:720] = 100
    assert visual.change_score(dark, webcam) < 15
    assert visual.change_score(dark, dark + 2) < 5


def test_rank_boosts_visual_peer_without_removing_exceptional_talking():
    originals = [candidate(0, 94), candidate(40, 71), candidate(80, 70), candidate(120, 12)]
    samples = [{"time": i + 10, "score": score} for i, score in [(0, 0), (40, 0), (80, 100), (120, 100)]]
    result = visual.rank(originals, samples)
    assert [c["start"] for c in result] == [0, 80, 40, 120]
    assert [c["score"] for c in result] == [94, 78, 71, 12]
    assert result[0]["visual_activity_level"] == "LOW"
    assert result[1]["visual_activity_level"] == "HIGH"
    assert { (c["start"], c["end"]) for c in result } == { (c["start"], c["end"]) for c in originals }
    assert originals[2]["score"] == 70
    assert visual.rank(result, samples) == result  # Never accumulate boosts.
    assert visual.rank([], samples) == []


def test_missing_samples_are_unknown_and_do_not_change_priority():
    result = visual.rank([candidate(0)], [])
    assert result[0]["score"] == 70
    assert result[0]["visual_activity_score"] is None
    assert result[0]["visual_activity_level"] is None
    medium = visual.rank([candidate(0)], [{"time": 10, "score": 40}])[0]
    assert medium["visual_activity_level"] == "MEDIUM"


@pytest.mark.parametrize("mode", MODES)
def test_visual_preserves_mode_selection_and_cluster_boundaries(mode):
    segments = [{"start": 30, "end": 55, "text": (
        "Olha isso, vou contar uma história. Meu Deus, eu não acredito! "
        "Que piada, todo mundo estava rindo. No final consegui, deu certo!"
    )}]
    before = detect(segments + segments, [0.03] * 1200, 1200, mode=mode)
    assert before
    after = visual.rank(before, [{"time": t, "score": 100} for t in range(10, 1200, 20)])
    assert [(c["start"], c["end"]) for c in after] == [(c["start"], c["end"]) for c in before]
    assert visual.rank(detect([], [0] * 1200, 1200, mode=mode), [{"time": 10, "score": 100}]) == []


def test_cache_reused_and_invalidated_by_source_or_version(tmp_path, monkeypatch):
    source, cache = tmp_path / "source.mp4", tmp_path / "visual.json"
    source.write_bytes(b"source")
    calls = []

    def frame(path, timestamp):
        calls.append(timestamp)
        return np.zeros(14400, dtype=np.uint8)

    monkeypatch.setattr(visual, "frame", frame)
    initial = visual.sample(source, 1200, cache)
    assert len(initial) == 60 and len(calls) == 120
    assert calls[:4] == [10, 11, 30, 31]
    assert visual.sample(source, 1200, cache) == initial
    assert len(calls) == 120
    source.write_bytes(b"changed source")
    visual.sample(source, 1200, cache)
    assert len(calls) == 240
    monkeypatch.setattr(visual, "VERSION", "next-version")
    visual.sample(source, 1200, cache)
    assert len(calls) == 360
    cache.write_text("broken", encoding="utf-8")
    visual.sample(source, 1200, cache)
    assert len(calls) == 480


def test_sampling_failure_does_not_cache_false_low(tmp_path, monkeypatch):
    source, cache = tmp_path / "source.mp4", tmp_path / "visual.json"
    source.touch()

    def fail(*args):
        raise ValueError("bad frame")

    monkeypatch.setattr(visual, "frame", fail)
    with pytest.raises(ValueError, match="bad frame"):
        visual.sample(source, 20, cache)
    assert not cache.exists()


def test_ffmpeg_seeks_before_input_and_reads_one_small_frame(monkeypatch):
    def run(command, **options):
        assert command.index("-ss") < command.index("-i")
        assert command[command.index("-frames:v") + 1] == "1"
        assert "scale=160:90" in command
        assert "gray" in command
        assert options["timeout"] == 30
        return subprocess.CompletedProcess(command, 0, bytes(14400))

    monkeypatch.setattr(visual.subprocess, "run", run)
    assert visual.frame("source.mp4", 400).size == 14400


def test_real_ffmpeg_static_and_moving_frames(tmp_path):
    scores = []
    for label, expression in [("static", "color=c=gray:s=160x90:r=10"),
                              ("moving", "testsrc2=s=160x90:r=10")]:
        source = tmp_path / f"{label}.mp4"
        subprocess.run([media.binary("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", expression,
                        "-t", "3", "-c:v", "libx264", str(source)], check=True,
                       capture_output=True, creationflags=media.FLAGS)
        scores.append(visual.sample(source, 3, tmp_path / f"{label}.json")[0]["score"])
    assert scores[0] == 0
    assert scores[1] > 15
