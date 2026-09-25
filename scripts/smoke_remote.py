"""Bounded public-source acceptance test; isolated database, never production records."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner import analysis  # noqa: E402
from miner.collector import Collector  # noqa: E402
from miner.service import Service  # noqa: E402

URL = "https://kick.com/gabepeixe/videos/01a0b055-85f0-79f1-94d4-c416add665b0"


def run():
    folder = ROOT / "test-results/remote-real"
    folder.mkdir(exist_ok=True)
    service = Service(ROOT, folder / "data")
    collector = Collector(service, output=folder / "TUTUCO-TV/04_RAW")
    report = {}
    started = time.monotonic()
    last = [0]
    def progress(n, message):
        if time.monotonic() - last[0] > 15:
            print(f"{n:.1f}% {message}", flush=True)
            last[0] = time.monotonic()
    try:
        report["discovery"] = collector.provider.discover("Kick", "gabepeixe", 3)
        public = collector.provider.metadata(URL)
        report["metadata"] = {k:v for k,v in public.items() if k != "sourceUrl"}
        existing = service.store.rows("SELECT id FROM remote_campaigns")
        rid = existing[0]["id"] if existing else collector.configure(dict(creator="gabepeixe", provider="Kick", channel="gabepeixe", start="2026-09-17", end="2026-09-17"))["id"]
        collector.manual(rid, [URL], lambda: None, progress)
        vid = collector.members(rid)[0]["id"]
        print("Public metadata and manual association OK; analyzing only 600..780 seconds plus context.", flush=True)
        report["analysis"] = collector.analyze(vid, {}, progress, window=(600, 780))
        rows = service.store.candidates(vid)
        report["candidates"] = rows
        report["temporary_bytes_after_analysis"] = collector.temp.usage()
        report["metrics"] = service.store.get_vod(vid)["analysis_metrics"]
        before = time.monotonic()
        report["warm"] = collector.analyze(vid, {}, progress, window=(600, 780))
        report["warm_seconds"] = time.monotonic() - before
        if rows:
            cid = rows[0]["id"]
            collector.review(rid, [cid], "APROVADO")
            report["raw"] = collector.export(cid, "raw", 5, 5, False, progress)
            report["exports"] = service.store.rows("SELECT * FROM exports WHERE candidate_id=?", (cid,))
            report["raw_details"] = [json.loads(Path(e["path"]).with_suffix(".json").read_text(encoding="utf-8")) for e in report["exports"]]
        report["temporary_bytes_after_raw"] = collector.temp.usage()
        report["seconds"] = time.monotonic() - started
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        analysis.save_json(folder / "report.json", report)
        service.executor.shutdown(wait=True)
        print(json.dumps({k:v for k,v in report.items() if k in ("error", "raw", "seconds", "warm_seconds", "temporary_bytes_after_analysis", "temporary_bytes_after_raw")}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    run()
