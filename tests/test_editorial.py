import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from miner import analysis, editorial, media, performance
from miner.preview_cache import PreviewCache
from miner.remote_provider import Provider
from test_remote import collector, configure, seed  # noqa: F401
from test_miner import video  # noqa: F401
from app import ROOT, create_app


def candidate():
    return dict(id="test", start=100, end=210, score=58, visual_activity_score=75)


def speech(*texts):
    return [dict(start=110 + i * 10, end=119 + i * 10, text=t) for i, t in enumerate(texts)]


@pytest.mark.parametrize(
    "texts,kind",
    [
        (
            ("Ele joga há dois anos, começou agora.", "Mesmo assim chegou na final do campeonato."),
            "COMPETITIVO",
        ),
        (("Eu era o armador do time.", "Mas não tinha comunicação e não consegui me adaptar."), "BASTIDOR"),
        (("Estávamos perdendo por três gols.", "No final viramos e vencemos a partida."), "COMPETITIVO"),
        (("Estou abrindo esse pacote de cartas.", "Veio um item lendário, não acredito!"), "REVEAL"),
    ],
)
def test_semantic_links_promote_low_old_score_without_quota(texts, kind):
    c = candidate()
    original = dict(c)
    r = editorial.review(c, speech(*texts), 1000)
    assert r["classification"] in ("RECOMENDADO", "BOM") and r["content_type"] == kind
    assert r["editorial_score"] > c["score"]
    assert c == original and (r["original_start"], r["original_end"]) == (100, 210)
    assert 20 <= r["suggested_duration"] <= 60
    assert r["title"] and r["hook"] and r["evidence"]
    assert all(
        editorial.review(c, speech(*texts), 1000)["classification"] == r["classification"] for _ in range(30)
    )


def test_backstage_good_without_payoff_and_negated_achievement_not_invented():
    r = editorial.review(
        candidate(),
        speech("Eu era o armador do time.", "Não consegui me adaptar e faltou comunicação."),
        1000,
    )
    assert r["payoff_score"] == 25 and r["classification"] == "RECOMENDADO"
    bad = editorial.review(
        candidate(), speech("Ele joga há dois anos.", "Ele não chegou na final do campeonato."), 1000
    )
    assert bad["classification"] not in ("RECOMENDADO", "BOM")
    isolated = editorial.review(candidate(), speech("Armador, final, dois anos, call, campeão, jogo."), 1000)
    assert isolated["classification"] not in ("RECOMENDADO", "BOM")


def test_distant_facts_and_motion_alone_do_not_form_story():
    rows = speech("Eu era o armador do time.", "Mas não tinha comunicação.")
    rows[1].update(start=195, end=205)
    assert not editorial.relations(rows, candidate())
    r = editorial.review({**candidate(), "visual_activity_score": 100}, [], 1000)
    assert r["classification"] not in ("RECOMENDADO", "BOM")
    assert r["suggested_start"] == 100 and r["suggested_end"] == 210


def test_identical_refined_ranges_group_without_losing_originals_or_decisions():
    import copy
    a = {**candidate(), "vod_id": "vod", "status": "NOVO", "editorial_review": {
        "editorial_score": 90, "classification": "RECOMENDADO", "suggested_start": 110, "suggested_end": 140}}
    b = {**a, "id": "neighbor", "start": 130, "end": 170,
         "editorial_review": {**a["editorial_review"], "editorial_score": 89}}
    originals = copy.deepcopy([a, b])
    grouped = editorial.group_refined([a, b])
    assert [a, b] == originals
    assert grouped[1]["refined_duplicate_of"] == a["id"]
    assert grouped[0]["refined_alternatives"] == [{"id": "neighbor", "start": 130, "end": 170}]
    for change in ({"vod_id": "other"}, {"status": "APROVADO"}, {"status": "DESCARTADO"},
                   {"editorial_package": {"recommended_start": 120, "recommended_end": 150}},
                   {"editorial_review": {**b["editorial_review"], "suggested_end": 155}}):
        assert not editorial.group_refined([a, {**b, **change}])[1]["refined_duplicate_of"]


# ---------------------------------------------------------------------------
# Tests for configurable tolerance in group_refined
# ---------------------------------------------------------------------------

def _cand(vid, cid, start, end, score, sugg_start, sugg_end, classification="RECOMENDADO",
          status="NOVO", **extra):
    """Minimal candidate dict with an editorial_review already attached."""
    return {
        "id": cid, "vod_id": vid, "start": start, "end": end, "score": score,
        "status": status, "editorial_review": {
            "editorial_score": score,
            "classification": classification,
            "suggested_start": sugg_start,
            "suggested_end": sugg_end,
        },
        **extra,
    }


def test_group_refined_overlapping_originals_within_tolerance_merge():
    """Two candidates with overlapping original windows that converge to the same
    editorial suggestion (within 3 s) are grouped under the higher-scoring one."""
    import copy
    a = _cand("vod1", "a", start=100, end=135, score=88, sugg_start=110, sugg_end=140)
    b = _cand("vod1", "b", start=118, end=150, score=85, sugg_start=112, sugg_end=142)
    originals = copy.deepcopy([a, b])
    grouped = editorial.group_refined([a, b])
    # originals must be untouched
    assert [a, b] == originals
    by_id = {g["id"]: g for g in grouped}
    # 'a' has higher score → representative; 'b' is the duplicate
    assert by_id["b"]["refined_duplicate_of"] == "a"
    assert by_id["a"]["refined_duplicate_of"] is None
    assert {"id": "b", "start": 118, "end": 150} in by_id["a"]["refined_alternatives"]


def test_group_refined_candidates_1_to_5s_apart_converging_to_same_suggestion():
    """Candidates whose original windows are 1-5 s apart but whose editorial
    review lands within 3 s of each other count as the same editorial moment."""
    # suggested ranges differ by exactly 2 s on each boundary → within 3.0 tolerance
    a = _cand("vod1", "a", start=100, end=130, score=82, sugg_start=105, sugg_end=130)
    b = _cand("vod1", "b", start=131, end=162, score=80, sugg_start=107, sugg_end=132)
    grouped = editorial.group_refined([a, b])
    by_id = {g["id"]: g for g in grouped}
    assert by_id["b"]["refined_duplicate_of"] == "a"
    # Difference of exactly 3 s is still within tolerance (boundary inclusive)
    c = _cand("vod1", "c", start=200, end=235, score=76, sugg_start=205, sugg_end=230)
    d = _cand("vod1", "d", start=204, end=240, score=74, sugg_start=208, sugg_end=233)
    grouped2 = editorial.group_refined([c, d])
    by_id2 = {g["id"]: g for g in grouped2}
    assert by_id2["d"]["refined_duplicate_of"] == "c"


def test_group_refined_narratively_distinct_adjacent_moments_are_not_merged():
    """Two candidates adjacent in time but with editorial suggestions > 3 s apart
    are preserved as separate entries: they represent different narrative moments."""
    # suggested ranges differ by 8 s (> default 3.0 tolerance)
    a = _cand("vod1", "a", start=100, end=130, score=88, sugg_start=105, sugg_end=130)
    b = _cand("vod1", "b", start=133, end=165, score=86, sugg_start=140, sugg_end=165)
    grouped = editorial.group_refined([a, b])
    by_id = {g["id"]: g for g in grouped}
    assert by_id["a"]["refined_duplicate_of"] is None
    assert by_id["b"]["refined_duplicate_of"] is None
    assert by_id["a"]["refined_alternatives"] == []
    # Candidates in completely different VODs are never merged regardless of closeness
    same_sugg_diff_vod = _cand("vod2", "c", start=105, end=132, score=90, sugg_start=105, sugg_end=130)
    grouped2 = editorial.group_refined([a, same_sugg_diff_vod])
    by_id2 = {g["id"]: g for g in grouped2}
    assert by_id2["a"]["refined_duplicate_of"] is None
    assert by_id2["c"]["refined_duplicate_of"] is None


def test_group_refined_best_candidate_is_always_representative():
    """The representative of the merged group must be the candidate with the
    highest editorial_score, regardless of input order."""
    low  = _cand("vod1", "low",  start=100, end=130, score=75, sugg_start=110, sugg_end=140)
    high = _cand("vod1", "high", start=112, end=145, score=91, sugg_start=111, sugg_end=141)
    mid  = _cand("vod1", "mid",  start=108, end=138, score=83, sugg_start=112, sugg_end=142)
    # Test all insertion orders: high should always be the representative
    for candidates in ([low, mid, high], [high, mid, low], [mid, high, low]):
        grouped = editorial.group_refined(candidates)
        by_id = {g["id"]: g for g in grouped}
        assert by_id["high"]["refined_duplicate_of"] is None, f"Order {[c['id'] for c in candidates]}"
        assert by_id["low"]["refined_duplicate_of"] == "high", f"Order {[c['id'] for c in candidates]}"
        assert by_id["mid"]["refined_duplicate_of"] == "high", f"Order {[c['id'] for c in candidates]}"
        assert len(by_id["high"]["refined_alternatives"]) == 2


def test_group_refined_strict_compat_with_half_second_tolerance():
    """Calling group_refined(candidates, tolerance=0.5) reproduces the original
    strict behaviour: candidates 2 s apart in suggestion are NOT merged."""
    a = _cand("vod1", "a", start=100, end=130, score=90, sugg_start=110, sugg_end=140)
    b = _cand("vod1", "b", start=118, end=150, score=88, sugg_start=112, sugg_end=142)
    # diff=2 s → NOT merged at tolerance=0.5
    grouped_strict = editorial.group_refined([a, b], tolerance=0.5)
    by_id_strict = {g["id"]: g for g in grouped_strict}
    assert by_id_strict["b"]["refined_duplicate_of"] is None, "tolerance=0.5 must not merge 2s-apart suggestions"
    # Same pair IS merged at default (3.0)
    grouped_default = editorial.group_refined([a, b])
    by_id_default = {g["id"]: g for g in grouped_default}
    assert by_id_default["b"]["refined_duplicate_of"] == "a", "default tolerance=3.0 must merge 2s-apart suggestions"



def test_cache_review_preserves_status_history_and_feedback(collector, monkeypatch):  # noqa: F811
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid, start=100)
    c.review(rid, [cid], "APROVADO", "Boa história; precisa ampliar contexto.")
    c.package(rid, cid, dict(title="Título humano", recommended_start=99, recommended_end=137))
    monkeypatch.setattr(
        editorial,
        "cached_segments",
        lambda *a: speech("Eu era o armador do time.", "Não tinha call e não consegui me adaptar."),
    )
    first = editorial.review_vod(c.store, vid)
    second = editorial.review_vod(c.store, vid)
    row = c.store.candidate(cid)
    assert first["cached"] == 0 and second["cached"] == 1
    assert row["status"] == "APROVADO" and row["start"] == 100 and row["end"] == 135
    assert row["editorial_package"]["title"] == "Título humano"
    feedback = c.store.rows("SELECT * FROM editorial_feedback")[0]
    assert feedback["note"] == "Boa história; precisa ampliar contexto."
    assert json.loads(feedback["snapshot"])["id"] == cid

    def cancel():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        editorial.review_vod(c.store, vid, cancel)
    assert c.store.candidate(cid) == row


def test_light_preview_refined_cache_and_raw_protection(collector, monkeypatch, video):  # noqa: F811
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid, start=1)
    c.store.update_vod(vid, duration=8)
    c.store.execute(
        "UPDATE candidates SET end=7,data=? WHERE id=?",
        (json.dumps({"editorial_review": {"suggested_start": 2, "suggested_end": 5}}), cid),
    )
    calls = []

    def download(url, target, start, end, quality, check, progress):
        calls.append((start, end, quality))
        media.clip(video, target, start, end, preview=True)
        return {"media": media.probe(target)}

    monkeypatch.setattr(c.provider, "download", download)
    c.export(cid, "preview", 0, 0, False, lambda *a: None)
    first = c.store.rows("SELECT * FROM exports")[0]
    path = Path(first["path"])
    c.export(cid, "preview", 0, 0, False, lambda *a: None)
    assert calls == [(2, 5, "preview")] and c.store.get_vod(vid)["preview_metrics"]["cache_hit"]
    c.store.execute(
        "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES('neighbor',?,2,5,80,'{}')", (vid,)
    )
    c.export("neighbor", "preview", 0, 0, False, lambda *a: None)
    assert calls == [(2, 5, "preview")], "Same VOD/range must reuse preview across candidate IDs"
    assert media.probe(path)["height"] <= 480
    raw = c.output / "BRKK" / "approved.mp4"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"RAW approved")
    c.store.execute(
        "INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,'raw',?,2,5)",
        (cid, vid, str(raw)),
    )
    os.utime(path, (time.time() - 20 * 86400,) * 2)
    assert c.previews.cleanup() == 1
    assert not path.exists() and raw.read_bytes() == b"RAW approved"
    c.export(cid, "preview", 0, 0, False, lambda *a: None)
    assert len(calls) == 2


def test_cleanup_refuses_raw_record_even_inside_preview_area(collector):  # noqa: F811
    c = collector
    rid = configure(c)
    vid, cid = seed(c, rid)
    cache = PreviewCache(c.store)
    path = cache.target(c.store.get_vod(vid), 0, 5)
    path.write_bytes(b"RAW")
    cache.commit(path)
    os.utime(path, (0, 0))
    c.store.execute(
        "INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,'raw',?,0,5)",
        (cid, vid, str(path)),
    )
    assert cache.cleanup() == 0 and path.read_bytes() == b"RAW"


def test_preview_provider_requests_360_variant_not_1080(monkeypatch, tmp_path):
    p = Provider(ROOT)
    requested = []
    commands = []

    def metadata(url, quality, check):
        requested.append(quality)
        return {
            "availableQualities": ["1080p60", "480p30", "360p30", "160p30"],
            "sourceUrl": "https://public.example/video.m3u8",
            "selectedQuality": quality,
        }

    monkeypatch.setattr(p, "metadata", metadata)
    monkeypatch.setattr(p, "execute", lambda args, *a: commands.append(args))
    monkeypatch.setattr(media, "probe", lambda *a: dict(width=640, height=360, fps=30, duration=30))
    p.download("https://kick.com/brkk/videos/test", tmp_path / "preview.mp4", 100, 130, "preview")
    assert requested == ["worst", "360p30"] and "*100.000-130.000" in commands[0]


@pytest.mark.parametrize("quality", ["1080p60", "unknown", ""])
def test_preview_refuses_unconfirmed_low_resolution(monkeypatch, tmp_path, quality):
    p = Provider(ROOT)
    monkeypatch.setattr(p, "metadata", lambda *a: {"selectedQuality": quality})
    monkeypatch.setattr(p, "execute", lambda *a: pytest.fail("Must not download high/unknown quality"))
    with pytest.raises(ValueError, match="variante leve"):
        p.download("https://kick.com/brkk/videos/test", tmp_path / "preview.mp4", 100, 130, "preview")


def test_preview_api_returns_cached_file_without_job(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    client = app.test_client()
    c = app.extensions["collector"]
    try:
        rid = configure(c)
        vid, cid = seed(c, rid)
        path = tmp_path / "preview.mp4"
        path.write_bytes(b"cached preview")
        c.store.execute(
            "INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,'preview',?,100,135)",
            (cid, vid, str(path)),
        )
        monkeypatch.setattr(c, "enqueue", lambda *a: pytest.fail("Cache hit must not enqueue"))
        c.store.execute(
            "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES('neighbor',?,100,135,80,'{}')", (vid,)
        )
        token = re.search(r'name="miner-token" content="([^"]+)"', client.get("/").text)[1]
        response = client.post(
            f"/api/remote/{rid}/action",
            json={"kind": "preview", "candidate_id": "neighbor"},
            headers={"X-Miner-Token": token},
        )
        assert response.status_code == 200 and response.json["cached"]
        assert "job" not in response.json and response.json["export"]["path"] == str(path)
    finally:
        app.extensions["miner"].executor.shutdown(wait=True)


def test_whisper_reused_between_regions_and_released_between_jobs(tmp_path, monkeypatch):
    instances = []

    class Model:
        def __init__(self, *a, **kw):
            instances.append(kw["device"])

        def transcribe(self, *a, **kw):
            return iter([SimpleNamespace(start=0, end=1, text="fala")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    monkeypatch.setattr(analysis, "ffmpeg", lambda *a: None)
    with performance.session():
        for i in range(2):
            analysis.transcribe(tmp_path / "audio.wav", tmp_path / f"region{i}", tmp_path / "models", 2)
        assert len(instances) == 1 and "whisper_load" in performance.timings()
    with performance.session():
        analysis.transcribe(tmp_path / "audio.wav", tmp_path / "region2", tmp_path / "models", 2)
    assert len(instances) == 2


def test_previews_batch_only_recommended_good_and_keeps_decisions(collector, monkeypatch):  # noqa: F811
    c = collector
    rid = configure(c)
    ids = []
    for i, label in enumerate(editorial.CLASSES, 1):
        vid, cid = seed(c, rid, i)
        ids.append(cid)
        c.store.execute(
            "UPDATE candidates SET data=? WHERE id=?",
            (json.dumps({"editorial_review": {"classification": label, "editorial_score": 90 - i}}), cid),
        )
    tasks = []
    exports = []
    monkeypatch.setattr(c.service.executor, "submit", tasks.append)
    monkeypatch.setattr(c, "export", lambda cid, *a: exports.append(cid))
    c.enqueue(rid, "shortlist_previews")
    tasks[0]()
    assert exports == ids[:2] and all(c.store.candidate(cid)["status"] == "NOVO" for cid in ids)
