"""Real operational mining script for GabePeixe Kick VOD (70-minute continuous block: 00:10:00 to 01:20:00)."""
import sys
import time
from pathlib import Path

# Ensure UTF-8 stdout/stderr on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from miner import analysis  # noqa: E402
from miner.collector import Collector  # noqa: E402
from miner.service import Service  # noqa: E402

URL = "https://kick.com/gabepeixe/videos/01a0ca21-3cb8-73d8-8b68-a47c5c51987a"
WINDOW_START = 600.0   # 00:10:00
WINDOW_END = 4800.0    # 01:20:00
WINDOW_DURATION = WINDOW_END - WINDOW_START  # 4200s (70 minutes)


def run():
    print("=" * 60)
    print("INICIANDO MINERACAO REAL - GABEPEIXE KICK")
    print(f"URL: {URL}")
    print(f"Janela: {WINDOW_START}s ({analysis.timestamp(WINDOW_START)}) -> {WINDOW_END}s ({analysis.timestamp(WINDOW_END)})")
    print(f"Duracao do bloco: {WINDOW_DURATION}s ({WINDOW_DURATION/60:.1f} minutos)")
    print("=" * 60)

    service = Service(ROOT, ROOT / "data")
    collector = Collector(service)
    started = time.perf_counter()

    last_print = [0]
    def progress(pct, msg):
        now = time.perf_counter()
        if now - last_print[0] >= 5 or pct >= 100:
            print(f"[{time.strftime('%H:%M:%S')}] [{pct:5.1f}%] {msg}", flush=True)
            last_print[0] = now

    report = {
        "url": URL,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "window_duration": WINDOW_DURATION,
        "window_start_formatted": analysis.timestamp(WINDOW_START),
        "window_end_formatted": analysis.timestamp(WINDOW_END),
    }

    try:
        # 1. Configurar campanha operacional
        print("\n[1/5] Configurando campanha operacional GabePeixe...")
        existing = service.store.rows("SELECT id FROM remote_campaigns WHERE json_extract(data, '$.creator') = 'gabepeixe'")
        if existing:
            rid = existing[0]["id"]
            print(f"Campanha existente reutilizada: {rid}")
        else:
            run_obj = collector.configure({
                "creator": "gabepeixe",
                "provider": "Kick",
                "channel": "gabepeixe",
                "start": "2026-09-01",
                "end": "2026-10-22",
                "name": "GabePeixe · Campeonato Kick 2026",
            })
            rid = run_obj["id"]
            print(f"Campanha criada: {rid}")
        report["run_id"] = rid

        # 2. Registrar VOD
        print("\n[2/5] Registrando VOD via Collector.manual...")
        collector.manual(rid, [URL], lambda: None, progress)
        members = collector.members(rid)
        vod = members[0]
        vid = vod["id"]
        title_safe = str(vod.get('title') or '').encode('ascii', 'replace').decode('ascii')
        print(f"VOD registrada: ID={vid}, Titulo='{title_safe}', Duracao={vod.get('duration')}s")
        report["vod_id"] = vid
        report["vod_title"] = vod.get("title")
        report["vod_duration"] = vod.get("duration")

        # 3. Executar Fast Scan e decupagem
        print(f"\n[3/5] Executando Collector.analyze para janela ({WINDOW_START}s -> {WINDOW_END}s)...")
        options = {
            "mining_mode": "equilibrado",
            "model": "base",
            "device": "cpu",
            "transcribe": True,
        }
        res_text = collector.analyze(vid, options, progress, check=lambda: None, window=(WINDOW_START, WINDOW_END))
        print(f"Resultado do analyze: {res_text}")
        report["analysis_message"] = res_text

        # 4. Métricas e temporários
        vod_updated = service.store.get_vod(vid)
        metrics = vod_updated.get("analysis_metrics", {})
        report["metrics"] = metrics
        report["temp_usage_bytes"] = collector.temp.usage()

        # 5. Candidatos e Classificação Editorial
        print("\n[4/5] Coletando candidatos e aplicando shortlist...")
        all_candidates = service.store.candidates(vid)
        report["raw_candidates_count"] = len(all_candidates)

        view_data = collector.view(rid)
        candidates_shortlist = view_data["candidates"]
        report["grouped_candidates_count"] = len(candidates_shortlist)

        distribution = {"RECOMENDADO": 0, "BOM": 0, "TALVEZ": 0, "FRACO": 0, "OUTRO": 0}
        for c in candidates_shortlist:
            cls = c.get("editorial_review", {}).get("classification", "OUTRO")
            distribution[cls] = distribution.get(cls, 0) + 1
        report["distribution"] = distribution

        elapsed_total = time.perf_counter() - started
        report["elapsed_total_seconds"] = elapsed_total
        report["elapsed_total_formatted"] = analysis.timestamp(elapsed_total)

        # Salvar relatório detalhado
        out_path = ROOT / "data/test_kick/mining_result.json"
        analysis.save_json(out_path, report)
        print(f"\n[5/5] Relatório salvo em: {out_path}")

        print("\n" + "=" * 60)
        print("RESUMO DA MINERAÇÃO REAL")
        print(f"Duração processada: {WINDOW_DURATION}s ({WINDOW_DURATION/60:.1f} min)")
        print(f"Tempo total gasto: {elapsed_total:.2f}s ({analysis.timestamp(elapsed_total)})")
        print(f"Chunks de Fast Scan: {metrics.get('chunks', 0)}")
        print(f"Regiões de fala/interesse: {metrics.get('regions', 0)}")
        print(f"Regiões profundas transcritas: {metrics.get('deep_regions', 0)}")
        print(f"Candidatos brutos: {len(all_candidates)}")
        print(f"Candidatos na shortlist (após group_refined): {len(candidates_shortlist)}")
        print(f"Distribuição: {distribution}")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}", flush=True)
        import traceback
        traceback.print_exc()
        report["error"] = str(e)
    finally:
        service.executor.shutdown(wait=True)


if __name__ == "__main__":
    run()
