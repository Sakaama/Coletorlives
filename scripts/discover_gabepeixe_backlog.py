import json
import sys
from pathlib import Path

from miner.collector import Collector, date_of
from miner.remote_provider import Provider
from miner.service import Service
from miner import backlog

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(".").resolve()
service = Service(ROOT, ROOT / "data")
provider = Provider(ROOT)
collector = Collector(service, provider)

print("Consultando VODs públicas do GabePeixe na Kick via any-dl (metadados apenas)...")
try:
    raw_vods = provider.discover("Kick", "gabepeixe", 100)
    print(f"Total de VODs retornadas pelo provider: {len(raw_vods)}")
except Exception as exc:
    print(f"Erro na descoberta: {exc}")
    raw_vods = []

# Filter for championship period >= 2026-09-01
period_vods = []
for v in raw_vods:
    d = date_of(v.get("startTime"))
    if d and d >= "2026-09-01":
        period_vods.append({
            "id": str(v.get("id")),
            "url": v.get("webUrl") or v.get("url"),
            "title": v.get("title") or "Sem título",
            "date": d,
            "date_time": v.get("startTime"),
            "duration": v.get("durationSec") or 0,
        })

sorted_vods = backlog.sort_backlog_vods(period_vods)
print(f"\nVODs dentro do regulamento do campeonato (>= 2026-09-01): {len(sorted_vods)}")

# Inspect against database
db_vods = service.store.rows("SELECT * FROM vods WHERE campaign='gabepeixe'")
print(f"VODs já cadastradas no banco: {len(db_vods)}")
for dv in db_vods:
    candidates = service.store.candidates(dv["id"])
    print(f"  - Banco: {dv['id']} | data={dv.get('date')} | remote_state={dv.get('remote_state')} | candidatos={len(candidates)}")

print("\n--- CATÁLOGO REAL E ORDEM DA FILA (MAIS RECENTE PRIMEIRO) ---")
for i, v in enumerate(sorted_vods, 1):
    # Check if in DB
    match = next((dv for dv in db_vods if dv.get("source_key") == v["url"] or json.loads(dv["data"]).get("provider_vod_id") == v["id"]), None)
    if match:
        c_count = len(service.store.candidates(match["id"]))
        st = "CONCLUÍDO (JÁ PROCESSADA)" if (match.get("remote_state") == "CONCLUÍDO" or c_count > 0) else match.get("remote_state", "PENDENTE")
        hours = v['duration'] / 3600
        print(f"#{i:02d}: {v['date']} | {v['title'][:45]} | {hours:.1f}h | Status: {st} ({c_count} candidatos) [ID: {match['id']}]")
    else:
        hours = v['duration'] / 3600
        print(f"#{i:02d}: {v['date']} | {v['title'][:45]} | {hours:.1f}h | Status: FILA (PENDENTE)")

service.executor.shutdown(wait=False)
