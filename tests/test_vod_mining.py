import json

import pytest

from app import create_app
from miner.vod_mining import MODES, detect, group_windows, overlap


def event(start, length=25):
    return [
        {
            "start": start,
            "end": start + 5,
            "text": "Olha isso, vou contar uma história que aconteceu naquela partida.",
        },
        {
            "start": start + 5,
            "end": start + length - 5,
            "text": "Meu Deus, eu não acredito! Que piada, todo mundo estava rindo daquela jogada.",
        },
        {
            "start": start + length - 5,
            "end": start + length,
            "text": "No final consegui vencer a partida e foi por isso que ganhei.",
        },
    ]


def test_overlapping_windows_and_exact_duplicates_are_grouped():
    windows = [
        {"start": 10, "end": 40, "tags": {"reação"}},
        {"start": 25, "end": 50, "tags": {"humor"}},
        {"start": 10, "end": 40, "tags": {"reação"}},
    ]
    assert len(group_windows(windows)) == 1
    assert group_windows(windows)[0]["end"] == 50
    assert len(windows) == 3


def test_nearby_same_event_merges_but_closed_events_remain_distinct():
    a = {"start": 0, "end": 20, "tags": {"storytelling"}}
    b = {"start": 24, "end": 40, "tags": {"storytelling"}}
    assert len(group_windows([a, b])) == 1
    assert len(group_windows([{**a, "closed": True}, b])) == 2
    found = detect(event(10) + event(60), [0.03] * 150, 150)
    assert len(found) == 2
    assert overlap(*found) == 0


def test_duplicate_transcript_segments_do_not_duplicate_or_boost_candidates():
    rows = event(10)
    assert detect(rows, [0.03] * 100, 100) == detect(rows + rows, [0.03] * 100, 100)


def test_dynamic_duration_follows_context_and_payoff():
    rows = event(10, 18) + event(130, 65)
    found = sorted(detect(rows, [0.03] * 240, 240), key=lambda c: c["start"])
    assert len(found) == 2
    assert found[0]["end"] >= 28 and found[1]["end"] >= 195
    assert found[1]["end"] - found[1]["start"] > 2 * (found[0]["end"] - found[0]["start"])
    assert all(c["end"] - c["start"] != 35 for c in found)
    assert "payoff" in found[0]["reason"]


def test_modes_differ_without_creating_quota_fillers():
    medium = [
        {
            "start": 10,
            "end": 30,
            "text": "A história aconteceu: na minha opinião, esse foi o pior jogo da temporada. No final acabou tudo bem.",
        }
    ]
    weak = [
        {
            "start": 100,
            "end": 125,
            "text": "Eu discordo dessa avaliação do jogo, isso é ridículo. No final consegui explicar o motivo para todos.",
        }
    ]
    counts = {m: len(detect(medium + weak, [0.03] * 200, 200, mode=m)) for m in MODES}
    assert counts["conservador"] < counts["equilibrado"] < counts["agressivo"]
    for mode in MODES:
        assert detect([], [0] * 1200, 1200, mode=mode) == []
    with pytest.raises(ValueError):
        detect([], [], 1200, mode="invalid")


def test_twenty_minutes_sufficient_events_density_not_quota():
    rows = sum((event(40 + i * 180) for i in range(6)), [])
    result = detect(rows, [0.03] * 1200, 1200)
    assert len(result) == 6
    assert len(detect(event(40), [0.03] * 1200, 1200)) == 1
    # Exceptional content can exceed the reference; there is no hard cap of eight.
    rich = sum((event(20 + i * 100) for i in range(11)), [])
    assert len(detect(rich, [0.03] * 1200, 1200)) == 11


def test_audio_alone_and_noise_do_not_dominate_text():
    audio = [0.002] * 1200
    audio[45] = 0.9
    assert detect([], audio, 1200) == []
    exploratory = detect([], audio, 1200, mode="agressivo")
    assert len(exploratory) == 1 and exploratory[0]["score"] <= 15
    clear = event(100)
    noisy = [{**s, "text": s["text"] + " [música] [inaudível]", "avg_logprob": -2} for s in clear]
    clean = detect(clear, [0.03] * 200, 200)
    bad = detect(noisy, [0.03] * 200, 200, mode="agressivo")
    assert not bad or bad[0]["score"] < clean[0]["score"]
    assert len(detect([], [0.9] * 1200, 1200)) == 0


def test_missing_payoff_and_silence_are_penalized():
    complete = event(20)
    incomplete = complete[:2]
    good = detect(complete, [0.03] * 200, 200, mode="agressivo")[0]
    bad = detect(incomplete, [0.03] * 200, 200, mode="agressivo")[0]
    assert good["score"] > bad["score"]
    assert "sem conclusão" in bad["reason"]
    quiet = detect(complete, [0] * 200, 200, mode="agressivo")[0]
    assert quiet["score"] < good["score"]
    assert "silêncio" in quiet["reason"]


@pytest.mark.parametrize("campaign", ["gabepeixe", "brkk", "brabox"])
@pytest.mark.parametrize("visual_available", [True, False])
def test_reanalysis_replaces_selection_and_preserves_campaign_history(tmp_path, monkeypatch, campaign, visual_available):
    app = create_app(tmp_path / "data")
    service = app.extensions["miner"]
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    monkeypatch.setattr(
        "miner.media.probe", lambda p: {"duration": 1200, "width": 640, "height": 360, "has_audio": True}
    )
    monkeypatch.setattr("miner.media.extract_audio", lambda *a: None)
    monkeypatch.setattr("miner.analysis.energy", lambda *a: [0.03] * 1200)
    monkeypatch.setattr("miner.analysis.transcribe", lambda *a: event(100))
    def sample(*args):
        if not visual_available:
            raise ValueError("unreadable video")
        return [{"time": 110, "score": 80}]

    monkeypatch.setattr("miner.visual_activity.sample", sample)
    try:
        vid = service.import_local(campaign, str(source))["vod"]["id"]
        for i in range(52):
            service.store.execute(
                "INSERT INTO candidates(id,vod_id,start,end,score,status,data) VALUES(?,?,?,?,?,?,?)",
                (
                    f"old{i}",
                    vid,
                    i * 10,
                    i * 10 + 35,
                    50,
                    "APROVADO" if i == 0 else "NOVO",
                    json.dumps({"reason": "anterior", "summary": "anterior"}),
                ),
            )
        raw = tmp_path / "raw.mp4"
        raw.write_bytes(b"keep-raw")
        service.store.execute(
            "INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,?,?,?,?)",
            ("old0", vid, "raw", str(raw), 0, 35),
        )
        service.analyze(vid, {"mining_mode": "equilibrado"}, lambda *a: None)
        active = service.store.candidates(vid)
        assert len(active) == 1
        assert active[0]["visual_activity_score"] == (80 if visual_available else None)
        assert active[0]["visual_activity_level"] == ("HIGH" if visual_available else None)
        assert active[0]["score"] == min(100, active[0]["editorial_score"] + (6 if visual_available else 0))
        assert len(service.store.candidates(vid, include_archived=True)) == 53
        assert service.store.candidate("old0")["status"] == "APROVADO"
        assert raw.read_bytes() == b"keep-raw" and source.read_bytes() == b"original"
        service.store.execute("UPDATE candidates SET status='DESCARTADO' WHERE id=?", (active[0]["id"],))
        service.analyze(vid, {"mining_mode": "equilibrado"}, lambda *a: None)
        assert service.store.candidates(vid)[0]["id"] == active[0]["id"]
        assert service.store.candidates(vid)[0]["status"] == "DESCARTADO"
        assert len(app.test_client().get(f"/api/vods/{vid}?history=1").json["candidates"]) == 53
        assert len(app.test_client().get(f"/api/vods/{vid}").json["candidates"]) == 1
        assert service.store.get_vod(vid)["campaign"] == campaign
    finally:
        service.executor.shutdown(wait=True)
