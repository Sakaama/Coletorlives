import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data/history.sqlite3')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT id, vod_id, start, end, score, status, data FROM candidates WHERE vod_id LIKE ? ORDER BY score DESC',
    ('%GABEPEIXE%',)
).fetchall()

print(f"Total candidates: {len(rows)}")
for i, r in enumerate(rows):
    d = json.loads(r["data"])
    er = d.get("editorial_review", {})
    start_fmt = f"{int(r['start']//3600):02d}:{int((r['start']%3600)//60):02d}:{int(r['start']%60):02d}"
    end_fmt = f"{int(r['end']//3600):02d}:{int((r['end']%3600)//60):02d}:{int(r['end']%60):02d}"
    print("=" * 60)
    print(f"[{i+1}] ID: {r['id']}")
    print(f"Intervalo: {r['start']}s -> {r['end']}s ({start_fmt} -> {end_fmt}, duração: {r['end']-r['start']:.1f}s)")
    print(f"Score do Minerador: {r['score']}")
    print(f"Editorial Score: {er.get('editorial_score')}")
    print(f"Classificação Editorial: {er.get('classification')}")
    print(f"Content Type: {er.get('content_type')}")
    print(f"Hook: {er.get('hook')}")
    print(f"Summary: {d.get('summary')}")
    print(f"Motivo Técnico: {d.get('reason')}")
    print(f"Motivo Editorial: {er.get('reason')}")
    print(f"Warnings: {er.get('warnings')}")
    print(f"Visual Boost: {d.get('visual_boost')} (Activity: {d.get('visual_activity_score')}, Level: {d.get('visual_activity_level')})")
