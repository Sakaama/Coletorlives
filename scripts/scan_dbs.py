import sqlite3
from pathlib import Path
from datetime import datetime

root = Path(r"D:\Projetos\TUTUCO-CLIP-MINER")
found = []
for p in root.rglob("*"):
    if p.suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        parts = p.parts
        if any(ign in parts for ign in ("test-results", ".venv", "__pycache__", ".pytest_cache")):
            continue
        found.append(p)

print(f"=== BANCOS ENCONTRADOS ({len(found)}) ===")
for p in found:
    stat = p.stat()
    dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    counts = {}
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in ("vods", "candidates", "jobs", "editorial_feedback", "remote_campaigns", "remote_vods"):
            if t in tables:
                counts[t] = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        conn.close()
    except Exception as e:
        counts["error"] = str(e)
    print(f"CAMINHO: {p}")
    print(f"TAMANHO: {stat.st_size} bytes ({stat.st_size/1024:.1f} KB)")
    print(f"DATA DE MODIFICACAO: {dt}")
    print(f"CONTAGENS: {counts}")
    print("-" * 50)
