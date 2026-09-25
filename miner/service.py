import json
import logging
import math
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


from miner import analysis, long_vod, media, range_download, visual_activity, ytdlp_cli, editorial
from miner.rules import eligibility, load_campaigns, validate_url
from miner.store import Store

LOG = logging.getLogger(__name__)


def number(value, low, high, label):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: informe um número.") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label}: use um valor entre {low} e {high}.")
    return value


class Service:
    def __init__(self, root, data=None):
        self.root = Path(root).resolve()
        self.store = Store(data or self.root / "data")
        self.campaigns = load_campaigns(self.root / "config" / "campaigns")
        for cid in self.campaigns:
            self.store.dirs(cid)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="miner")
        self.lock = threading.Lock()
        self.active = set()
        from miner.remote_provider import Provider
        self.provider = Provider(self.root)
        self.store.execute(
            "UPDATE jobs SET state='INTERROMPIDO', message='Aplicativo reiniciado. Repita a ação para retomar os arquivos concluídos.' WHERE state IN ('FILA','EXECUTANDO')"
        )

    def campaign(self, cid):
        if cid not in self.campaigns:
            raise ValueError("Campanha inválida.")
        return self.campaigns[cid]

    def create_vod(self, campaign, key, data):
        self.campaign(campaign)
        known = self.store.rows("SELECT id FROM vods WHERE campaign=? AND source_key=?", (campaign, key))
        if known:
            return self.store.get_vod(known[0]["id"]), True
        vid = f"{campaign.upper()}_{datetime.now():%Y-%m-%d}_{uuid.uuid4().hex[:10]}"
        self.store.execute(
            "INSERT INTO vods(id,campaign,source_key,data) VALUES(?,?,?,?)",
            (vid, campaign, key, json.dumps(data, ensure_ascii=False)),
        )
        self.store.dirs(campaign, vid)
        return self.store.get_vod(vid), False

    def submit(self, vid, kind, function):
        self.store.get_vod(vid)
        with self.lock:
            if vid in self.active:
                raise ValueError("Já existe uma tarefa em andamento para esta VOD. Aguarde sua conclusão.")
            self.active.add(vid)
        jid = uuid.uuid4().hex
        self.store.execute("INSERT INTO jobs(id,vod_id,kind,state) VALUES(?,?,?,'FILA')", (jid, vid, kind))

        def progress(value, message="Processando…"):
            self.store.execute(
                "UPDATE jobs SET progress=?,message=? WHERE id=?", (round(value, 1), message, jid)
            )

        def work():
            try:
                self.store.execute("UPDATE jobs SET state='EXECUTANDO' WHERE id=?", (jid,))
                message = function(progress)
                self.store.execute(
                    "UPDATE jobs SET state='CONCLUÍDO',progress=100,message=? WHERE id=?",
                    (message or "Concluído.", jid),
                )
            except Exception as exc:
                LOG.exception("Falha na tarefa %s / %s", jid, vid)
                self.store.execute(
                    "UPDATE jobs SET state='ERRO',message=? WHERE id=?",
                    (
                        str(exc)[-2200:]
                        + " Os arquivos concluídos foram preservados. Você pode tentar novamente.",
                        jid,
                    ),
                )
            finally:
                with self.lock:
                    self.active.discard(vid)

        self.executor.submit(work)
        return jid

    def import_url(self, campaign, url):
        platform, url = validate_url(url)
        rules = self.campaign(campaign)
        if (rules.get("original_lives_only") or platform == "Twitch") and platform not in rules[
            "allowed_sources"
        ]:
            raise ValueError("Fonte não permitida nesta campanha. Confira as fontes nas regras.")
        vod, known = self.create_vod(
            campaign,
            url,
            {
                "url": url,
                "platform": platform,
                "title": "Aguardando metadados",
                "eligibility": {"status": "REVISÃO HUMANA", "reasons": ["Metadados pendentes."]},
            },
        )
        job = None if known else self.submit(vod["id"], "metadados", lambda p: self.metadata(vod["id"], p))
        return {"vod": vod, "known": known, "job": job}

    def metadata(self, vid, progress):
        vod = self.store.get_vod(vid)
        if not vod.get("url"):
            raise ValueError("Arquivo local não possui metadados remotos.")
        progress(10, "Consultando metadados, sem baixar a VOD…")
        info = ytdlp_cli.extract_info(self.root, vod["url"], download=False)
        if info.get("is_live"):
            raise ValueError("Esta transmissão ainda está ao vivo. Importe a gravação após seu término.")
        release = info.get("release_timestamp") if info.get("was_live") else None
        date = datetime.fromtimestamp(release, UTC).date().isoformat() if release else None
        if not date and info.get("upload_date"):
            date = datetime.strptime(info["upload_date"], "%Y%m%d").date().isoformat()
        changes = {
            "title": info.get("title") or "Título indisponível",
            "channel": info.get("channel") or info.get("uploader"),
            "channel_id": info.get("channel_id") or info.get("uploader_id"),
            "duration": info.get("duration"),
            "date": date,
            "date_kind": "live" if release else "upload",
            "description": (info.get("description") or "")[:10000],
            "was_live": info.get(
                "was_live", None if self.campaign(vod["campaign"]).get("original_lives_only") else False
            ),
        }
        changes["eligibility"] = eligibility(self.campaign(vod["campaign"]), {**vod, **changes})
        self.store.update_vod(vid, **changes)
        analysis.save_json(
            self.store.dirs(vod["campaign"], vid)["vods"] / "metadata.json", {**vod, **changes}
        )
        return "Metadados obtidos. Confira a elegibilidade antes de baixar."

    def import_local(self, campaign, path, title=None, date=None, existing=None):
        self.campaign(campaign)
        source = Path(path).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in (
            ".mp4",
            ".mkv",
            ".mov",
            ".webm",
            ".avi",
            ".m4v",
            ".ts",
        ):
            raise ValueError("Selecione um vídeo local existente (MP4, MKV, MOV, WEBM, AVI, M4V ou TS).")
        info = media.probe(source)
        if info["duration"] <= 0:
            raise ValueError("Não foi possível determinar a duração deste arquivo.")
        if date:
            datetime.strptime(date, "%Y-%m-%d")
        key = f"local:{str(source).casefold()}:{source.stat().st_size}:{source.stat().st_mtime_ns}"
        changes = {
            **info,
            "local_path": str(source),
            "title": title or source.stem,
            "date": date or None,
            "date_kind": "human" if date else None,
            "platform": "Local",
        }
        if existing:
            vod = self.store.get_vod(existing)
            changes = {**info, "local_path": str(source)}
            self.store.update_vod(existing, **changes)
            return {"vod": self.store.get_vod(existing), "known": False}
        changes["eligibility"] = eligibility(self.campaign(campaign), changes)
        vod, known = self.create_vod(campaign, key, changes)
        analysis.save_json(
            self.store.dirs(campaign, vod["id"])["vods"] / "source.json",
            {"path": str(source), "note": "Original referenciado; não mover este arquivo."},
        )
        return {"vod": vod, "known": known}

    def download(self, vid, progress):
        vod = self.store.get_vod(vid)
        if vod.get("local_path") and Path(vod["local_path"]).is_file():
            return "VOD já disponível localmente. Download reutilizado."
        folder = self.store.dirs(vod["campaign"], vid)["vods"]

        ytdlp_cli.extract_info(self.root, vod["url"], download=True, folder=folder, progress=progress)
        files = [
            p
            for p in folder.glob("source.*")
            if p.suffix in (".mp4", ".mkv", ".webm", ".mov") and ".f" not in p.stem
        ]
        if not files:
            raise ValueError("Download não produziu um vídeo utilizável. Use a opção de arquivo local.")
        source = max(files, key=lambda p: p.stat().st_size)
        self.store.update_vod(vid, local_path=str(source), **media.probe(source))
        return "Download concluído. Pronto para analisar."

    def analyze(self, vid, options, progress):
        started = time.perf_counter()
        metrics = {}
        vod = self.store.get_vod(vid)
        source = vod.get("local_path")
        if not source or not Path(source).exists():
            raise ValueError("Baixe a VOD ou vincule um arquivo local antes de analisar.")
        info = media.probe(source)
        preparation_seconds = time.perf_counter() - started
        self.store.update_vod(vid, **info)
        dirs = self.store.dirs(vod["campaign"], vid)
        energies, segments, warnings = [], [], []
        model = options.get("model", "base")
        if model not in ("tiny", "base", "small"):
            raise ValueError("Modelo inválido.")
        mode = options.get("mining_mode", "equilibrado")
        from miner.vod_mining import MODES

        if mode not in MODES:
            raise ValueError("Modo de garimpo inválido.")
        if info["duration"] > 1800 or options.get("pipeline") == "long":
            found, warnings, metrics, has_segments = long_vod.run(
                source, dirs["transcripts"], self.root / "models", info, options, progress
            )
            segments = [True] if has_segments else []
            if warnings and not found:
                self.store.update_vod(vid, warnings=warnings, analysis_metrics=metrics)
                raise ValueError(" ".join(warnings) + " Seleção anterior preservada.")
        else:
            audio = dirs["transcripts"] / "audio.wav"
            if info["has_audio"]:
                media.extract_audio(
                    source, audio, info["duration"], lambda n: progress(n * 0.2, "Extraindo áudio…")
                )
                energies = analysis.energy(
                    audio,
                    dirs["transcripts"] / "energy.json",
                    lambda n: progress(20 + n * 0.1, "Medindo energia do áudio…"),
                )
                if options.get("transcribe", True):
                    try:
                        segments = analysis.transcribe(
                            audio,
                            dirs["transcripts"],
                            self.root / "models",
                            info["duration"],
                            model,
                            options.get("device", "cpu"),
                            lambda n, m: progress(30 + n * 0.6, m),
                        )
                    except Exception as exc:
                        LOG.exception("Transcrição incompleta")
                        warnings.append(
                            "Transcrição não concluída: "
                            + str(exc)[:500]
                            + ". Sem contexto textual suficiente pode não haver candidatos; tente analisar novamente."
                        )
                else:
                    warnings.append("Análise sem transcrição, conforme selecionado.")
            else:
                warnings.append("Vídeo sem áudio: sem evidência suficiente para selecionar momentos.")
            progress(93, "Organizando candidatos por prioridade…")
            found = analysis.detect(segments, energies, info["duration"], mode=mode)
            if found:
                samples = []
                try:
                    samples = visual_activity.sample(
                        source, info["duration"], dirs["candidates"] / "visual_activity.json",
                        lambda n: progress(93 + n * 0.05, "Amostrando atividade visual…"),
                    )
                except Exception:
                    LOG.exception("Atividade visual indisponível")
                    warnings.append("Atividade visual indisponível; prioridade editorial preservada.")
                found = visual_activity.rank(found, samples)
        metrics["preparation"] = preparation_seconds
        metrics["total"] = time.perf_counter() - started
        return self.save_analysis(vid, found, warnings, metrics, model, mode, bool(segments))

    def save_analysis(self, vid, found, warnings, metrics, model, mode, has_segments):
        started = time.perf_counter()
        vod = self.store.get_vod(vid)
        dirs = self.store.dirs(vod["campaign"], vid)
        generation = uuid.uuid4().hex[:8]
        existing = self.store.candidates(vid, include_archived=True)
        analysis.save_json(dirs["candidates"] / f"analysis_{generation}.json", found)
        # Commit the current selection atomically; retain all past decisions and exports.
        used = set()
        with self.store.connect() as db:
            for old in existing:
                data = json.loads(
                    db.execute("SELECT data FROM candidates WHERE id=?", (old["id"],)).fetchone()[0]
                )
                data["archived"] = True
                db.execute(
                    "UPDATE candidates SET data=? WHERE id=?",
                    (json.dumps(data, ensure_ascii=False), old["id"]),
                )
            for candidate in found:
                same = next(
                    (
                        c
                        for c in existing
                        if c["id"] not in used
                        and abs(c["start"] - candidate["start"]) < 0.05
                        and abs(c["end"] - candidate["end"]) < 0.05
                    ),
                    None,
                )
                data = {k: v for k, v in candidate.items() if k not in ("start", "end", "score")}
                data.update(generation=generation, archived=False)
                if same:
                    if same.get("editorial_package"):
                        data["editorial_package"] = same["editorial_package"]
                    used.add(same["id"])
                    db.execute(
                        "UPDATE candidates SET score=?,data=? WHERE id=?",
                        (candidate["score"], json.dumps(data, ensure_ascii=False), same["id"]),
                    )
                else:
                    db.execute(
                        "INSERT INTO candidates(id,vod_id,start,end,score,data) VALUES(?,?,?,?,?,?)",
                        (
                            uuid.uuid4().hex[:16],
                            vid,
                            candidate["start"],
                            candidate["end"],
                            candidate["score"],
                            json.dumps(data, ensure_ascii=False),
                        ),
                    )
        self.store.update_vod(
            vid,
            analyzed=True,
            warnings=warnings,
            transcript_model=model if has_segments else None,
            mining_mode=mode,
            analysis_generation=generation,
            analysis_metrics={**metrics, "persist_seconds": time.perf_counter() - started},
        )
        editorial.review_vod(self.store, vid)
        return (
            f"Análise concluída: {len(found)} candidatos atuais ({mode}). Análises anteriores preservadas no histórico. "
            + " ".join(warnings)
            + " Tempos: " + "; ".join(f"{k}: {analysis.timestamp(v)}" for k, v in metrics.items() if k in ("audio", "visual", "fast_scan", "transcription", "deep_analysis", "deduplication", "ranking", "total"))
        )

    def bounds(self, candidate, pre, post):
        vod = self.store.get_vod(candidate["vod_id"])
        start = max(0, candidate["start"] - number(pre, 0, 120, "Pré-roll"))
        end = min(vod["duration"], candidate["end"] + number(post, 0, 120, "Pós-roll"))
        if end <= start:
            raise ValueError("Intervalo de corte inválido.")
        return start, end

    def export(self, vid, ids, kind, pre, post, progress, remote=None):
        started = time.perf_counter()
        notes = []
        vod = self.store.get_vod(vid)
        if not vod.get("local_path") and kind != "prep":
            raise ValueError("VOD local indisponível.")
        dirs = self.store.dirs(vod["campaign"], vid)
        for index, cid in enumerate(ids):
            c = self.store.candidate(cid)
            if c["vod_id"] != vid:
                raise ValueError("Candidato não pertence à VOD.")
            if kind in ("raw", "prep") and c["status"] != "APROVADO":
                raise ValueError("Aprove os candidatos antes de extrair RAW ou PREP.")
            package, suggestion = c.get("editorial_package", {}), c.get("editorial_review", {})
            cut = {**c, "start": package.get("recommended_start", suggestion.get("suggested_start", c["start"])),
                   "end": package.get("recommended_end", suggestion.get("suggested_end", c["end"]))}
            start, end = self.bounds(cut if kind in ("preview", "raw") else c, pre, post)

            def report(n, index=index):
                return progress(
                    (index + n / 100) / len(ids) * 100, f"Gerando {kind.upper()} {index + 1}/{len(ids)}…"
                )

            if kind == "preview":
                target = dirs["candidates"] / f"{cid}_{start:.2f}_{end:.2f}_preview.mp4"
                media.clip(vod["local_path"], target, start, end, preview=True, progress=report)
            elif kind == "raw":
                target = (
                    dirs["raw"]
                    / f"{cid}_{analysis.timestamp(start).replace(':', '')}_score{c['score']}_{uuid.uuid4().hex[:6]}.mp4"
                )
                if remote:
                    if not remote.get("aligned"):
                        raise ValueError("Confirme que o proxy começa no tempo zero da VOD original.")
                    url = remote.get("url") or vod.get("url")
                    platform, url = validate_url(url or "")
                    if platform not in self.campaign(vod["campaign"])["allowed_sources"]:
                        raise ValueError("Fonte não permitida pela campanha.")
                    try:
                        notes.append(range_download.obtain(self.root, url, target, start, end, progress))
                    except Exception as exc:
                        LOG.exception("RAW remoto indisponível; usando original local")
                        notes.append(f"Fallback local: {exc} Qualidade da fonte local preservada, sem promessa de 1080p60.")
                        media.clip(vod["local_path"], target, start, end, progress=report)
                else:
                    media.clip(vod["local_path"], target, start, end, progress=report)
            elif kind == "prep":
                raws = self.store.rows(
                    "SELECT * FROM exports WHERE candidate_id=? AND kind='raw' ORDER BY id DESC", (cid,)
                )
                if not raws:
                    raise ValueError("Extraia o RAW deste candidato antes de gerar o PREP.")
                if not vod.get("camera"):
                    raise ValueError("Configure a região da câmera desta VOD primeiro.")
                raw = raws[0]
                start, end = raw["start"], raw["end"]
                target = dirs["prep"] / f"{cid}_{uuid.uuid4().hex[:8]}_vertical.mp4"
                preset = {**self.campaign(vod["campaign"])["vertical"], **vod.get("vertical", {})}
                content = vod.get("content") or {
                    "x": 0,
                    "y": 0,
                    "width": vod["width"],
                    "height": vod["height"],
                }
                raw_info = media.probe(raw["path"])
                sx, sy = raw_info["width"] / vod["width"], raw_info["height"] / vod["height"]
                def scaled(rect, sx=sx, sy=sy):
                    return {key: round(value * (sx if key in ("x", "width") else sy)) for key, value in rect.items()}
                media.prep(raw["path"], target, scaled(vod["camera"]), scaled(content), preset, end - start, report)
            else:
                raise ValueError("Tipo de exportação inválido.")
            self.store.execute(
                "INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,?,?,?,?)",
                (cid, vid, kind, str(target), start, end),
            )
        elapsed = time.perf_counter() - started
        LOG.info("Etapa %s: %.3fs", kind, elapsed)
        self.store.update_vod(vid, export_metrics={**vod.get("export_metrics", {}), kind: elapsed})
        return f"{len(ids)} arquivo(s) {kind.upper()} disponível(is). Tempo: {analysis.timestamp(elapsed)}. " + " ".join(notes)

    def discover(self, campaign_id, url, limit=50):
        from miner.discovery import discover_source
        c = self.campaign(campaign_id)
        limit = int(number(limit, 1, 100, "Limite de descoberta"))
        return discover_source(self.provider, c, url, limit=limit, store=self.store)
