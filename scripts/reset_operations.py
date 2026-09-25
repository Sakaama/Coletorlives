"""Offline only. Backup first; explicit IDs and optional known test imports only."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from miner.instance import acquire  # noqa: E402
from miner.maintenance import backup, reset  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", default=[])
    parser.add_argument("--test-source", action="append", default=[])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    lock = acquire(ROOT / "data/.instance.lock")
    if lock is None:
        parser.error("Encerre o aplicativo antes do backup/reset.")
    target = backup(ROOT / "data", args.backup)
    print("Backup validado:", target, flush=True)
    if args.apply:
        if not args.ids:
            parser.error("Informe explicitamente os IDs de teste.")
        reset(ROOT / "data", target, args.ids, args.test_source)
        print("Reset concluído; configurações, campanhas e originais externos preservados.")
