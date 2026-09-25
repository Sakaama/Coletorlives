import json
from pathlib import Path
from types import SimpleNamespace
import sys
import wave
import numpy as np

import pytest

from miner import analysis, long_vod as long


def event(start):
    return [{"start": start, "end": start + 8, "text": "Olha isso, vou contar uma história."},
            {"start": start + 8, "end": start + 23, "text": "Meu Deus, não acredito! Que piada, todo mundo rindo."},
            {"start": start + 23, "end": start + 35, "text": "No final consegui, ganhei, deu certo!"}]


def test_chunks_cover_twelve_hours_and_fractional_tail():
    parts = long.chunks(43200.004)
    assert len(parts) == 72
    assert parts[0] == (0, 600) and parts[-1] == (42600, 43200.004)
    assert all(a[1] == b[0] for a, b in zip(parts, parts[1:], strict=False))
    assert long.absolute([{"start": 1062, "end": 1080, "text": "resultado"}], 21600)[0]["start"] == 22662


def test_fast_scan_is_not_final_and_uniform_motion_is_not_an_event():
    values = [0.03] * 1200
    uniform = [{"time": t, "score": 80} for t in range(10, 1200, 20)]
    assert long.promising(values, uniform, 1200) == []
    changing = [{"time": 10, "score": 10}, {"time": 30, "score": 90}, {"time": 50, "score": 20}]
    assert long.promising(values, changing, 1200)
    assert analysis.detect([], values, 1200) == []
    assert long.promising([0] * 1200, changing, 1200) == []


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    source = tmp_path / "proxy.mp4"
    source.write_bytes(b"proxy")
    calls = {"visual": [], "speech": [], "audio": []}
    def ffmpeg(args, target, *unused):
        target = Path(target)
        if not target.exists():
            calls["audio"].append(str(target))
            target.write_bytes(b"audio")
        return target
    def energy(audio, cache, *args):
        return [0.03] * 600
    def visual(source, duration, cache, progress=None, offset=0):
        calls["visual"].append(offset)
        return [{"time": offset + t, "score": 90 if t % 60 == 30 else 10} for t in range(10, int(duration), 20)]
    def speech(audio, folder, models, duration, model, device, progress):
        cache = Path(folder) / model / "transcript.json"
        if cache.exists():
            return json.loads(cache.read_text())
        calls["speech"].append(str(folder))
        offset = float(Path(folder).name.split("_")[1])
        rows = [{**s, "start": s["start"] - offset, "end": s["end"] - offset}
                for s in event(585) + event(1000) if offset <= s["start"] and s["end"] <= offset + duration]
        cache.parent.mkdir(exist_ok=True)
        analysis.save_json(cache, rows)
        return rows
    monkeypatch.setattr("miner.media.ffmpeg", ffmpeg)
    monkeypatch.setattr(long, "region_audio", lambda base, source, target, start, end, duration: ffmpeg([], target))
    monkeypatch.setattr("miner.analysis.energy", energy)
    monkeypatch.setattr("miner.visual_activity.sample", visual)
    monkeypatch.setattr("miner.analysis.transcribe", speech)
    def run(duration=1200, **options):
        return long.run(source, tmp_path / "work", tmp_path / "models", {"duration": duration, "has_audio": True}, options, lambda *a: None)
    return run, calls, source, visual


def test_cross_chunk_event_global_dedup_rank_and_cache(pipeline):
    run, calls, source, _ = pipeline
    found, warnings, metrics, _ = run()
    assert not warnings and len(found) == 2
    assert sum(c["start"] < 600 < c["end"] for c in found) == 1
    assert all(0 <= c["start"] < c["end"] <= 1200 for c in found)
    assert [c["score"] for c in found] == sorted((c["score"] for c in found), reverse=True)
    before = {k: len(v) for k, v in calls.items()}
    again, _, warm, _ = run(mining_mode="agressivo")
    assert again and warm["chunks_cached"] == 2 and warm["fast_scan_cached"]
    assert before == {k: len(v) for k, v in calls.items()}
    source.write_bytes(b"different proxy")
    run()
    assert len(calls["visual"]) == 4


def test_resume_after_process_interruption(pipeline, monkeypatch):
    run, calls, source, visual = pipeline
    def interrupt(source, duration, cache, progress=None, offset=0):
        if offset == 600:
            raise KeyboardInterrupt()
        return visual(source, duration, cache, progress, offset)
    monkeypatch.setattr("miner.visual_activity.sample", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run()
    monkeypatch.setattr("miner.visual_activity.sample", visual)
    found, warnings, metrics, _ = run()
    assert found and not warnings and metrics["chunks_cached"] == 1
    assert calls["visual"] == [0, 600]


def test_deep_region_failure_is_visible_and_retry_reuses_success(pipeline, monkeypatch):
    run, calls, _, _ = pipeline
    real = analysis.transcribe
    def fail(audio, folder, *args):
        if "speech_255." in str(folder):
            raise RuntimeError("region failed")
        return real(audio, folder, *args)
    monkeypatch.setattr(analysis, "transcribe", fail)
    _, warnings, metrics, _ = run()
    assert warnings and metrics["deep_regions"] < 4
    monkeypatch.setattr(analysis, "transcribe", real)
    found, warnings, metrics, _ = run()
    assert found and not warnings and metrics["transcription_cached"] >= 3


def test_dedup_segments_keeps_separate_occurrences():
    rows = event(100)
    shifted = [{**s, "start": s["start"] + 0.2, "end": s["end"] + 0.2} for s in rows]
    assert len(long.dedup_segments(rows + shifted + event(800))) == 6


def test_proxy_pcm_slice_crosses_chunks_with_exact_duration(tmp_path, monkeypatch):
    monkeypatch.setitem(long.CONFIG, "chunk", 2)
    for i in range(2):
        folder = tmp_path / f"scan_{i:05}"
        folder.mkdir()
        with wave.open(str(folder / "audio.wav"), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(np.full(32000, 100 + i, dtype="<i2").tobytes())
    target = tmp_path / "region.wav"
    long.region_audio(tmp_path, "unused-proxy", target, 1.5, 2.5, 4)
    with wave.open(str(target), "rb") as audio:
        data = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
    assert len(data) == 16000
    assert np.all(data[:8000] == 100) and np.all(data[8000:] == 101)


def test_twelve_hour_silent_fixture_uses_zero_deep_transcription(pipeline, monkeypatch):
    run, calls, _, _ = pipeline
    monkeypatch.setattr(analysis, "energy", lambda *a: [0] * 600)
    found, warnings, metrics, _ = run(duration=43200)
    assert not found and not warnings
    assert metrics["chunks"] == 72 and metrics["regions"] == 0
    assert not calls["speech"]
    _, _, warm, _ = run(duration=43200)
    assert warm["chunks_cached"] == 72 and warm["fast_scan_cached"]


def test_editorial_config_reuses_measurements_model_changes_only_speech(pipeline, monkeypatch):
    run, calls, _, _ = pipeline
    run()
    before = {k: len(v) for k, v in calls.items()}
    monkeypatch.setitem(long.CONFIG, "audio_ratio", 3.0)
    run()
    assert len(calls["visual"]) == before["visual"]
    assert len(calls["audio"]) == before["audio"]
    run(model="tiny")
    assert len(calls["speech"]) > before["speech"]
    assert len(calls["visual"]) == before["visual"]


@pytest.mark.parametrize("fail_at", ["load", "inference"])
def test_existing_cuda_failure_falls_back_to_cpu(tmp_path, monkeypatch, fail_at):
    devices = []
    class Model:
        def __init__(self, name, device, **kwargs):
            self.device = device
            devices.append(device)
            if device == "cuda" and fail_at == "load":
                raise RuntimeError("CUDA unavailable")
        def transcribe(self, *args, **kwargs):
            if self.device == "cuda":
                raise RuntimeError("CUDA OOM")
            return iter([SimpleNamespace(start=1, end=2, text="fala")]), None
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(analysis, "ffmpeg", lambda *a: None)
    result = analysis.transcribe(tmp_path / "audio.wav", tmp_path / "cache", tmp_path / "models", 10, device="cuda")
    assert result[0]["start"] == 1 and devices == ["cuda", "cpu"]
