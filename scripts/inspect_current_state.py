import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

db = sqlite3.connect("file:data/history.sqlite3?mode=ro", uri=True)
db.row_factory = sqlite3.Row

print("PRAGMA integrity_check:", db.execute("PRAGMA integrity_check").fetchall()[0][0])

vods = db.execute("""
    SELECT id, 
           json_extract(data, '$.date') as dt, 
           json_extract(data, '$.remote_state') as st,
           json_extract(data, '$.duration') as dur,
           json_extract(data, '$.title') as title 
    FROM vods 
    WHERE campaign='gabepeixe' 
    ORDER BY dt DESC
""").fetchall()

print(f"\nTotal VODs GabePeixe no banco: {len(vods)}")
for r in vods:
    c_count = db.execute("SELECT COUNT(*) FROM candidates WHERE vod_id=?", (r["id"],)).fetchone()[0]
    dur_h = (r["dur"] or 0) / 3600
    print(f"Live: {r['dt']} | {r['id']} | dur: {dur_h:4.1f}h | status: {str(r['st']):10} | candidatos: {c_count:2d} | {r['title'][:40]}")

tot_cands_gp = db.execute("SELECT COUNT(*) FROM candidates WHERE vod_id LIKE 'GABEPEIXE%'").fetchone()[0]
tot_cands_all = db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
print(f"\nTotal candidatos GabePeixe: {tot_cands_gp}")
print(f"Total candidatos Geral: {tot_cands_all}")

# Check remote_jobs
print("\n--- REMOTE JOBS ---")
jobs = db.execute("SELECT id, run_id, kind, state, progress, message, created FROM remote_jobs WHERE run_id='2137c0d0e8d54b67' ORDER BY created DESC").fetchall()
for j in jobs:
    print(f"Job: {j['id']} | kind: {j['kind']} | state: {j['state']} | progress: {j['progress']}% | created: {j['created']}")
    print(f"  message: {j['message']}")

db.close()
