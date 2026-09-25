import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

db = sqlite3.connect("file:data/history.sqlite3?mode=ro", uri=True)
db.row_factory = sqlite3.Row

vods = [
    ("2026-09-22", "GABEPEIXE_2026-09-23_f63dcd9eb1"),
    ("2026-09-20", "GABEPEIXE_2026-09-23_e8cd09d9a8"),
    ("2026-09-19", "GABEPEIXE_2026-09-23_41a7e2c751"),
    ("2026-09-18", "GABEPEIXE_2026-09-23_c946376eea"),
    ("2026-09-17", "GABEPEIXE_2026-09-23_e1de9ceec8"),
    ("2026-09-15", "GABEPEIXE_2026-09-23_d92df58ca4"),
    ("2026-09-13", "GABEPEIXE_2026-09-23_9d91aece2b"),
]

print("=" * 80)
print("DETALHAMENTO DAS 7 VODS CONCLUÍDAS PELO BACKLOG RUNNER")
print("=" * 80)

for live_date, vid in vods:
    v_row = db.execute("SELECT data FROM vods WHERE id=?", (vid,)).fetchone()
    v_data = json.loads(v_row["data"])
    dur_h = (v_data.get("duration") or 0) / 3600
    title = v_data.get("title")
    
    cands = db.execute("SELECT data, score FROM candidates WHERE vod_id=?", (vid,)).fetchall()
    classes = {}
    for c in cands:
        cd = json.loads(c["data"])
        cl = cd.get("editorial_review", {}).get("classification") or "SEM_REVIEW"
        classes[cl] = classes.get(cl, 0) + 1
    
    print(f"Live: {live_date} | Duração: {dur_h:.1f}h | Total Cortes: {len(cands):2d}")
    print(f"  Classificações: {classes}")
    print(f"  Título: {title}")
    print(f"  VOD ID: {vid}")
    print("-" * 80)

db.close()
