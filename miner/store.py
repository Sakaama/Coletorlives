import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "history.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS vods (
                    id TEXT PRIMARY KEY, campaign TEXT NOT NULL, source_key TEXT NOT NULL,
                    created TEXT DEFAULT CURRENT_TIMESTAMP, data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS vod_source ON vods(campaign, source_key);
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, vod_id TEXT NOT NULL REFERENCES vods(id),
                    start REAL NOT NULL, end REAL NOT NULL, score INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'NOVO', data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS candidate_vod ON candidates(vod_id);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, vod_id TEXT NOT NULL REFERENCES vods(id),
                    kind TEXT NOT NULL, state TEXT NOT NULL, progress REAL DEFAULT 0,
                    message TEXT DEFAULT '', created TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS exports (
                    id INTEGER PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id),
                    vod_id TEXT NOT NULL REFERENCES vods(id), kind TEXT NOT NULL,
                    path TEXT NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
                    created TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS editorial_feedback (
                    id INTEGER PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id),
                    status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', snapshot TEXT NOT NULL,
                    created TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, args).fetchall()]

    def execute(self, sql, args=()):
        with self.connect() as db:
            db.execute(sql, args)

    def get_vod(self, vid):
        rows = self.rows("SELECT * FROM vods WHERE id=?", (vid,))
        if not rows:
            raise ValueError("VOD não encontrada.")
        row = rows[0]
        data = json.loads(row.pop("data"))
        return {**row, **data}

    def update_vod(self, vid, **changes):
        with self.connect() as db:
            row = db.execute("SELECT data FROM vods WHERE id=?", (vid,)).fetchone()
            data = json.loads(row[0])
            data.update(changes)
            db.execute("UPDATE vods SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), vid))

    def candidate(self, cid):
        rows = self.rows("SELECT * FROM candidates WHERE id=?", (cid,))
        if not rows:
            raise ValueError("Candidato não encontrado.")
        row = rows[0]
        data = json.loads(row.pop("data"))
        return {**row, **data}

    def candidates(self, vid, include_archived=False):
        result = []
        exports = self.rows("SELECT * FROM exports WHERE vod_id=? AND kind='raw'", (vid,))
        for row in self.rows("SELECT * FROM candidates WHERE vod_id=? ORDER BY score DESC, start", (vid,)):
            row.update(json.loads(row.pop("data")))
            if row.get("archived") and not include_archived:
                continue
            row["exports"] = self.rows("SELECT * FROM exports WHERE candidate_id=?", (row["id"],))
            row["duplicate"] = any(
                max(0, min(row["end"], e["end"]) - max(row["start"], e["start"]))
                / max(0.001, min(row["end"] - row["start"], e["end"] - e["start"]))
                >= 0.65
                for e in exports
            )
            result.append(row)
        return result

    def dirs(self, campaign, vid=None):
        base = self.root / "campaigns" / campaign
        result = {}
        for kind in ("vods", "transcripts", "candidates", "raw", "prep"):
            path = base / kind
            if vid:
                path /= vid
            path.mkdir(parents=True, exist_ok=True)
            result[kind] = path
        return result
