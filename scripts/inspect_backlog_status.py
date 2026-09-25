import sys
from pathlib import Path

from miner.collector import Collector
from miner.service import Service

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(".").resolve()
service = Service(ROOT, ROOT / "data")
collector = Collector(service)

bv = collector.backlog_view("2137c0d0e8d54b67")
bl = bv["backlog"]

print("=" * 60)
print("RELATÓRIO DE STATUS — BACKLOG GABEPEIXE (2137c0d0e8d54b67)")
print("=" * 60)
print(f"Total VODs na campanha: {bl['total_found']}")
print(f"Concluídas: {bl['completed_count']}")
print(f"Processando agora: {'1' if bl.get('processing') else '0'}")
print(f"Na fila (pendentes): {bl['pending_count']}")
print(f"Falharam: {bl['failed_count']}")
print(f"Candidatos aguardando revisão: {bl['candidates_waiting']}")
print(f"Shortlists prontas: {bl['shortlists_ready']}")

print("\n--- 1. VODS CONCLUÍDAS ---")
for i, v in enumerate(bl["completed"], 1):
    c_count = v.get("candidates_count", 0)
    print(f"[{i:02d}] {v.get('date')} | {v.get('title')[:45]} | {c_count} candidatos | ID: {v.get('id')}")

print("\n--- 2. VOD EM PROCESSAMENTO ATIVO ---")
p = bl.get("processing")
if p:
    print(f"-> {p.get('date')} | {p.get('title')} | ID: {p.get('id')}")
else:
    print("Nenhuma VOD em processamento ativo.")

print("\n--- 3. VODS NA FILA PENDENTE (EM ORDEM DECRESCENTE) ---")
for i, v in enumerate(bl["upcoming"], 1):
    print(f"[{i:02d}] {v.get('date')} | {v.get('title')[:45]} | ID: {v.get('id')}")

print("\n--- 4. VODS COM FALHA ---")
for i, v in enumerate(bl["failed"], 1):
    print(f"[{i:02d}] {v.get('date')} | {v.get('title')[:45]} | Erro: {v.get('remote_error')} | ID: {v.get('id')}")

print("\n--- 5. JOB ATIVO DO RUNNER ---")
rj = bv.get("running_job")
if rj:
    print(f"Job ID: {rj.get('id')}")
    print(f"Estado: {rj.get('state')}")
    print(f"Progresso: {rj.get('progress')}%")
    print(f"Mensagem: {rj.get('message')}")
    print(f"Criado em: {rj.get('created')}")
else:
    print("Nenhum job de backlog ativo no momento.")

service.executor.shutdown(wait=False)
