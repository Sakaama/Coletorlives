import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

db = sqlite3.connect("file:data/history.sqlite3?mode=ro", uri=True)
db.row_factory = sqlite3.Row

print("=" * 80)
print("HISTÓRICO DE CONCLUSÃO DAS VODS DO GABEPEIXE (ORDEM CRONOLÓGICA DE PROCESSAMENTO)")
print("=" * 80)

query = """
SELECT 
    v.id, 
    json_extract(v.data, '$.date') as live_date,
    json_extract(v.data, '$.title') as title,
    json_extract(v.data, '$.remote_state') as remote_state,
    json_extract(v.data, '$.duration') as duration,
    MIN(c.created) as first_candidate,
    MAX(c.created) as last_candidate,
    COUNT(c.id) as candidate_count
FROM vods v
LEFT JOIN candidates c ON v.id = c.vod_id
WHERE v.campaign = 'gabepeixe'
GROUP BY v.id
ORDER BY CASE WHEN last_candidate IS NULL THEN 1 ELSE 0 END, last_candidate ASC
"""

rows = db.execute(query).fetchall()

for i, r in enumerate(rows, 1):
    dur_h = (r['duration'] or 0) / 3600
    st = r['remote_state'] or 'PENDENTE'
    print(f"[{i:02d}] Live: {r['live_date']} | Duração: {dur_h:4.1f}h | Status: {st:10} | Candidatos: {r['candidate_count']:2d} | Conclusão: {r['last_candidate'] or 'N/A'}")
    print(f"     Título: {r['title']}")
    print(f"     ID: {r['id']}")
    print("-" * 80)
