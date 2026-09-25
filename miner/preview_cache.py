"""Only owned lightweight previews expire; RAW/import paths are never traversed."""
import hashlib
import json
import time
from pathlib import Path

from miner.analysis import save_json


class PreviewCache:
    def __init__(self, store):
        self.store = store
        self.root = store.root / "preview_cache"
        self.root.mkdir(exist_ok=True)

    def target(self, vod, start, end):
        key = hashlib.sha256(json.dumps(["preview360-1", vod["id"], vod.get("url"), vod.get("local_path"), start, end]).encode()).hexdigest()
        if self.root.is_symlink() or self.root.is_junction():
            raise ValueError("Cache de Preview não aceita links.")
        return self.root / (key + ".mp4")

    def commit(self, path):
        save_json(Path(path).with_suffix(".json"), {"owner": "preview360-1", "created": time.time()})

    def cleanup(self, days=14):
        if self.root.is_symlink() or self.root.is_junction():
            return 0
        removed = 0
        for marker in self.root.glob("*.json"):
            path = marker.with_suffix(".mp4")
            if marker.is_symlink() or path.is_symlink() or not path.is_file():
                continue
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                if data.get("owner") != "preview360-1" or path.stat().st_mtime > time.time()-days*86400:
                    continue
                rows = self.store.rows("SELECT kind FROM exports WHERE path=?", (str(path),))
                if not rows or any(r["kind"] != "preview" for r in rows):
                    continue
                path.unlink()
                marker.unlink()
                removed += 1
            except (OSError, ValueError):
                continue
        return removed
