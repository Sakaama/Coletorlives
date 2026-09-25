"""Review existing records only. Optional previews are bounded; never mines a VOD."""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner import editorial, media  # noqa: E402
from miner.collector import Collector  # noqa: E402
from miner.service import Service  # noqa: E402
from miner.store import Store  # noqa: E402


def stable(store):
    rows = store.rows("SELECT * FROM candidates ORDER BY id")
    for r in rows:
        d = json.loads(r["data"])
        d.pop("editorial_review", None)
        r["data"] = d
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def run(previews=False):
    store = Store(ROOT / "data")
    for table in ("jobs", "remote_jobs"):
        if store.rows(f"SELECT id FROM {table} WHERE state IN ('FILA','EXECUTANDO')"):
            raise ValueError("Há tarefas ativas; aguarde antes do benchmark.")
    before = stable(store)
    feedback = store.rows("SELECT * FROM editorial_feedback ORDER BY id")
    raw = store.rows("SELECT * FROM exports WHERE kind IN ('raw','prep')")
    raw_hashes = {r["path"]: hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() for r in raw if Path(r["path"]).is_file()}
    report = {"vods": [], "previews": []}
    ranked = []
    for row in store.rows("SELECT id FROM vods WHERE campaign='brkk'"):
        vid = row["id"]
        report["vods"].append({"id": vid, "old_metrics": store.get_vod(vid).get("analysis_metrics"),
                               "review": editorial.review_vod(store, vid), "warm": editorial.review_vod(store, vid)})
        ranked.extend(store.candidates(vid))
    ranked.sort(key=lambda c: (-c["editorial_review"]["editorial_score"], c["start"], c["id"]))
    report["counts"] = dict(Counter(c["editorial_review"]["classification"] for c in ranked))
    report["ranking"] = [{"position": i+1, "id": c["id"], "vod_id": c["vod_id"], "old_score": c["score"], **c["editorial_review"]} for i,c in enumerate(ranked)]
    # Human benchmark references used only for reporting/limited preview validation, never scoring.
    examples = [r for r in report["ranking"] if r["id"] in ("5a4e7f07b8df44b4", "46242afa4ceb4800")]
    report["positive_examples"] = examples
    if previews:
        service = Service(ROOT)
        collector = Collector(service)
        try:
            for c in examples:
                cid = c["id"]
                started = time.perf_counter()
                result = collector.export(cid, "preview", 0, 0, False, lambda *a: None)
                cold = time.perf_counter()-started
                cold_metrics = store.get_vod(c["vod_id"])["preview_metrics"]
                started = time.perf_counter()
                cached = collector.export(cid, "preview", 0, 0, False, lambda *a: None)
                warm = time.perf_counter()-started
                export = store.rows("SELECT * FROM exports WHERE candidate_id=? AND kind='preview' ORDER BY id DESC", (cid,))[0]
                report["previews"].append({"candidate": cid, "cold": cold, "warm": warm, "result": result, "cached": cached,
                                           "metrics": cold_metrics, "file": export, "probe": media.probe(export["path"]), "bytes": Path(export["path"]).stat().st_size})
                print(json.dumps(report["previews"][-1], ensure_ascii=True), flush=True)
        finally:
            service.executor.shutdown(wait=True)
    assert stable(store) == before, "Originals/status/manual packages changed"
    assert feedback == store.rows("SELECT * FROM editorial_feedback ORDER BY id"), "Feedback changed"
    assert raw == store.rows("SELECT * FROM exports WHERE kind IN ('raw','prep')")
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p,digest in raw_hashes.items())
    report["originals_feedback_and_raw_preserved"] = True
    (ROOT / "test-results/editorial-benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts":report["counts"], "examples":[{k:c[k] for k in ('position','editorial_score','classification','suggested_start','suggested_end')} for c in examples]},ensure_ascii=True),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--previews", action="store_true", help="Generate only the two short human benchmark examples")
    run(parser.parse_args().previews)
