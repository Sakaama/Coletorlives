"""Small operational campaign layer over the existing VOD store and executor."""
import json
import re
import shutil
import uuid
import time
from datetime import UTC, date, datetime
from pathlib import Path

from miner import analysis, backlog, editorial, long_vod, media, performance
from miner.preview_cache import PreviewCache
from miner.remote_analysis import RemoteSource
from miner.remote_provider import Cancelled, Provider, youtube_source
from miner.remote_temp import Temporaries
from miner.rules import eligibility, validate_url
from miner.service import number


def now():
    return datetime.now(UTC).isoformat()


def date_of(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).date().isoformat()
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    return None


class Collector:
    def __init__(self, service, provider=None, output=None):
        self.service, self.store = service, service.store
        self.provider = provider or Provider(service.root)
        self.temp = Temporaries(self.store.root)
        self.previews = PreviewCache(self.store)
        self.previews.cleanup()
        self.output = Path(output or service.root / "TUTUCO-TV/04_RAW").resolve()
        with self.store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS remote_campaigns(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS remote_vods(run_id TEXT NOT NULL REFERENCES remote_campaigns(id),
                  vod_id TEXT NOT NULL REFERENCES vods(id), PRIMARY KEY(run_id,vod_id));
                CREATE TABLE IF NOT EXISTS remote_jobs(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES remote_campaigns(id),
                  kind TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,progress REAL DEFAULT 0,
                  message TEXT DEFAULT '',cancel_requested INTEGER DEFAULT 0,created TEXT NOT NULL);
                UPDATE remote_jobs SET state='INTERROMPIDO',message='Reinicie a ação para retomar checkpoints.'
                  WHERE state IN ('FILA','EXECUTANDO');
            """)
            try:
                db.execute("ALTER TABLE remote_jobs ADD COLUMN pause_requested INTEGER DEFAULT 0")
            except Exception:
                pass
        self.temp.cleanup()

    def get(self, rid):
        rows = self.store.rows("SELECT * FROM remote_campaigns WHERE id=?", (rid,))
        if not rows:
            raise ValueError("Campanha operacional não encontrada.")
        return {"id": rid, **json.loads(rows[0]["data"])}

    def update(self, rid, **changes):
        data = self.get(rid)
        data.update(changes)
        self.store.execute("UPDATE remote_campaigns SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), rid))

    def configure(self, body, rid=None):
        campaign = self.service.campaign(body.get("creator"))
        provider, channel = body.get("provider"), str(body.get("channel", "")).strip()
        if provider not in campaign["allowed_sources"]:
            raise ValueError("Provider não permitido nas regras desta campanha.")
        if provider == "YouTube":
            channel = youtube_source(channel)
        elif not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", channel):
            raise ValueError("Informe o nome público do canal, sem URL ou caracteres especiais.")
        start, end = date.fromisoformat(str(body.get("start", ""))).isoformat(), date.fromisoformat(str(body.get("end", ""))).isoformat()
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("Data inicial posterior à final.")
        if rid:
            old = self.get(rid)
            if any(old[k] != v for k, v in [("creator", campaign["id"]), ("provider", provider), ("channel", channel)]):
                raise ValueError("Para outra fonte/criador, cadastre outra campanha operacional.")
            if self.active(rid):
                raise ValueError("Aguarde a tarefa terminar antes de alterar o período.")
        else:
            rid = uuid.uuid4().hex[:16]
            self.store.execute("INSERT INTO remote_campaigns(id,data) VALUES(?,?)", (rid, "{}"))
        self.update(rid, creator=campaign["id"], provider=provider, channel=channel, start=start, end=end,
                    name=str(body.get("name") or f"{campaign['name']} · {start} a {end}")[:120])
        return self.get(rid)

    def active(self, rid):
        return self.store.rows("SELECT id FROM remote_jobs WHERE run_id=? AND state IN ('FILA','EXECUTANDO')", (rid,))

    def register(self, rid, metadata, manual=False):
        run = self.get(rid)
        platform, url = validate_url(metadata.get("webUrl") or metadata.get("url") or "")
        if platform != run["provider"]:
            raise ValueError("A URL pertence a outro provider; crie a campanha operacional correspondente.")
        actual_date = date_of(metadata.get("startTime"))
        if actual_date and not run["start"] <= actual_date <= run["end"]:
            raise ValueError("VOD fora do período configurado.")
        if metadata.get("kind", "vod") != "vod":
            raise ValueError("Somente VODs gravadas são aceitas.")
        duration = metadata.get("durationSec")
        duration = number(duration, 0.1, 7 * 86400, "Duração") if duration is not None else None
        changes = {"url": url, "platform": platform, "provider_vod_id": str(metadata.get("id") or url.rsplit("/", 1)[-1]),
                   "title": metadata.get("title") or "Metadados pendentes", "channel": metadata.get("channel") or run["channel"],
                   "date": actual_date, "date_time": metadata.get("startTime"), "duration": duration,
                   "channel_id": metadata.get("channel_id"),
                   "date_kind": metadata.get("date_kind", "upload" if platform == "YouTube" else "live" if actual_date else None),
                   "was_live": metadata.get("was_live", True if actual_date and platform != "YouTube" else None),
                   "remote": True, "remote_state": "PENDENTE", "manual_url": manual}
        changes["eligibility"] = eligibility(self.service.campaign(run["creator"]), changes)
        if changes["eligibility"]["status"] == "NÃO PERMITIDA":
            changes["remote_state"] = "BLOQUEADO"
        known = self.store.rows("SELECT id FROM vods WHERE campaign=? AND source_key=?", (run["creator"], url))
        if not known and metadata.get("id"):
            known = self.store.rows("SELECT id FROM vods WHERE campaign=? AND json_extract(data,'$.platform')=? AND json_extract(data,'$.provider_vod_id')=?",
                                    (run["creator"], platform, str(metadata["id"])))
        if known:
            vid = known[0]["id"]
            if metadata.get("catalog_discovery") and not manual:
                self.store.execute("INSERT OR IGNORE INTO remote_vods(run_id,vod_id) VALUES(?,?)", (rid, vid))
                return vid, False, False
            old = self.store.get_vod(vid)
            # Discovery does not replace local attachments, reviews or completed work.
            if old.get("duration") == duration and changes["remote_state"] != "BLOQUEADO":
                previous = old.get("remote_state")
                changes["remote_state"] = ("CONCLUÍDO" if old.get("analyzed") else "PENDENTE") if previous in (None, "BLOQUEADO") else previous
            if all(old.get(k) == v for k, v in changes.items()):
                changed = False
            else:
                self.store.update_vod(vid, **changes)
                changed = True
        else:
            vod, _ = self.service.create_vod(run["creator"], url, changes)
            vid, changed = vod["id"], True
        self.store.execute("INSERT OR IGNORE INTO remote_vods(run_id,vod_id) VALUES(?,?)", (rid, vid))
        return vid, not bool(known), changed

    def members(self, rid):
        run = self.get(rid)
        vods = [self.store.get_vod(r["vod_id"]) for r in self.store.rows("SELECT vod_id FROM remote_vods WHERE run_id=?", (rid,))]
        filtered = [v for v in vods if not v.get("date") or run["start"] <= v["date"] <= run["end"]]
        return backlog.sort_backlog_vods(filtered)

    def view(self, rid):
        run, vods = self.get(rid), self.members(rid)
        rows = []
        for vod in vods:
            for c in self.store.candidates(vod["id"]):
                c.update(creator=vod["campaign"], vod_title=vod["title"], date=vod.get("date"), url=vod.get("url"))
                c.setdefault("type", "VISUAL" if c.get("visual_activity_level") in ("HIGH", "MEDIUM") else "TALKING")
                rows.append(c)
        rows.sort(key=lambda c: (-c.get("editorial_review", {}).get("editorial_score", c["score"]), c["start"], c["id"]))
        unique = []
        for c in rows:
            if not any(c["vod_id"] == old["vod_id"] and
                       max(0, min(c["end"], old["end"]) - max(c["start"], old["start"])) /
                       max(0.01, min(c["end"] - c["start"], old["end"] - old["start"])) >= 0.65 for old in unique):
                unique.append(c)
        return {"campaign": run, "vods": vods, "candidates": editorial.group_refined(unique),
                "summary": {"found": len(vods), "hours": sum(v.get("duration") or 0 for v in vods) / 3600,
                            "processed": sum(v.get("remote_state") == "CONCLUÍDO" for v in vods),
                            "pending": sum(v.get("remote_state") not in ("CONCLUÍDO", "BLOQUEADO") for v in vods),
                            "blocked": sum(v.get("remote_state") == "BLOQUEADO" for v in vods),
                            "candidates": len(unique), "approved": sum(c["status"] == "APROVADO" for c in unique),
                            "raws": sum(e["kind"] == "raw" for c in unique for e in c["exports"])},
                "jobs": self.store.rows("SELECT * FROM remote_jobs WHERE run_id=? ORDER BY created DESC LIMIT 100", (rid,)),
                "temporary_bytes": self.temp.usage()}

    @performance.session()
    def sync(self, rid, check, progress):
        run = self.get(rid)
        if run["provider"] == "YouTube":
            msg = "YouTube: descoberta automática desacoplada de VODs. Use a aba Descobrir no painel principal para consultar e importar."
            self.update(rid, last_sync=now(), sync_message=msg)
            return msg
        with performance.measure("discovery"):
            rows = self.provider.discover(run["provider"], run["channel"], 100, check)
        added = changed = 0
        for index, row in enumerate(rows):
            check()
            published = date_of(row.get("startTime"))
            if published and run["start"] <= published <= run["end"]:
                _, fresh, update = self.register(rid, row)
                added += fresh
                changed += update
            progress((index + 1) / max(1, len(rows)) * 100, "Sincronizando metadados…")
        note = " Listagem limitada a 100 VODs; use URLs manuais para períodos mais antigos." if len(rows) >= 100 else ""
        undated = sum(not row.get("startTime") for row in rows)
        if undated:
            note += f" {undated} VOD(s) sem data não incluída(s) automaticamente; confira e inclua a URL manualmente."
        self.update(rid, last_sync=now(), sync_metrics=performance.timings(), sync_message=f"{added} nova(s), {changed} registro(s) atualizado(s)." + note)
        return self.get(rid)["sync_message"]

    def manual(self, rid, urls, check, progress):
        for url in urls:
            check()
            # The job payload preserves the submitted URL. Create a pending VOD only on failure,
            # since providers can return a different canonical URL for the same recording.
            _, url = validate_url(url)
            known = self.store.rows("SELECT id FROM vods WHERE campaign=? AND source_key=?", (self.get(rid)["creator"], url))
            try:
                metadata = self.provider.metadata(url, check=check)
                if known:
                    metadata = {**metadata, "webUrl": url}
                self.register(rid, metadata, manual=True)
            except ValueError as exc:
                if known:
                    vid = known[0]["id"]
                    self.store.execute("INSERT OR IGNORE INTO remote_vods(run_id,vod_id) VALUES(?,?)", (rid, vid))
                else:
                    vid, _, _ = self.register(rid, {"webUrl": url}, manual=True)
                state = self.store.get_vod(vid).get("remote_state")
                self.store.update_vod(vid, remote_state=state if state == "CONCLUÍDO" else "ERRO", remote_error=str(exc))
                raise
        return f"{len(urls)} URL(s) incluída(s)."

    def analyze(self, vid, options, progress, check=lambda: None, window=None):
        from miner.vod_mining import MODES
        if options.get("mining_mode", "equilibrado") not in MODES:
            raise ValueError("Modo de garimpo inválido.")
        vod = self.store.get_vod(vid)
        if not vod.get("duration"):
            raise ValueError("Metadados/duração indisponíveis. Sincronize ou inclua a URL novamente; arquivo local continua disponível.")
        if vod.get("eligibility", {}).get("status") == "NÃO PERMITIDA":
            raise ValueError("VOD não permitida pelas regras atuais da campanha.")
        options = {"model": "base", "device": "cpu", "transcribe": True, **options}
        options["device"] = "cpu"
        if options["model"] not in ("tiny", "base", "small"):
            raise ValueError("Modelo inválido.")
        self.store.update_vod(vid, remote_state="EXECUTANDO")
        adapter = RemoteSource(vod, self.provider, self.temp, check, progress, window)
        try:
            found, warnings, metrics, has_segments = long_vod.run(vod["url"], self.store.dirs(vod["campaign"], vid)["transcripts"],
                self.service.root / "models", {"duration": vod["duration"], "has_audio": True}, options, progress, adapter=adapter)
            if not found and warnings:
                raise ValueError(" ".join(warnings))
            result = self.service.save_analysis(vid, found, warnings, metrics, options["model"], options.get("mining_mode", "equilibrado"), has_segments)
            self.store.update_vod(vid, remote_state="PARCIAL" if warnings or window else "CONCLUÍDO", remote_error="", remote_completed=now())
            return result
        except Cancelled:
            self.store.update_vod(vid, remote_state="PENDENTE", remote_error="Cancelado; checkpoints preservados.")
            raise
        except Exception as exc:
            self.store.update_vod(vid, remote_state="ERRO", remote_error=str(exc))
            raise

    def mine(self, rid, options, check, progress):
        pending = [v for v in self.members(rid) if v.get("remote_state") not in ("CONCLUÍDO", "BLOQUEADO")]
        errors = []
        for index, vod in enumerate(pending):
            check()
            vid = vod["id"]
            with self.service.lock:
                if vid in self.service.active:
                    errors.append(f"{vid}: já em andamento")
                    continue
                self.service.active.add(vid)
            try:
                self.analyze(vid, options, lambda n, m, index=index: progress((index + n / 100) / len(pending) * 100, f"VOD {index + 1}/{len(pending)} · {m}"), check)
            except Exception as exc:
                errors.append(f"{vid}: {exc}")
            finally:
                with self.service.lock:
                    self.service.active.discard(vid)
        if errors:
            raise ValueError("Pendências preservadas para retry: " + " | ".join(errors)[:1800])
        return f"{len(pending)} VOD(s) processada(s). Concluídas anteriores não foram refeitas."

    def candidate_ids(self, rid, ids):
        allowed = {v["id"] for v in self.members(rid)}
        ids = list(dict.fromkeys(ids))
        if not ids or len(ids) > 500:
            raise ValueError("Selecione de 1 a 500 candidatos.")
        rows = [self.store.candidate(cid) for cid in ids]
        if any(c["vod_id"] not in allowed for c in rows):
            raise ValueError("Candidato não pertence a esta campanha operacional.")
        return rows

    def review(self, rid, ids, status, feedback=""):
        if status not in ("NOVO", "APROVADO", "DESCARTADO"):
            raise ValueError("Status inválido.")
        rows = self.candidate_ids(rid, ids)
        if any(c["vod_id"] in self.service.active for c in rows):
            raise ValueError("Aguarde a mineração da VOD terminar.")
        with self.store.connect() as db:
            for c in rows:
                db.execute("UPDATE candidates SET status=? WHERE id=?", (status, c["id"]))
                db.execute("INSERT INTO editorial_feedback(candidate_id,status,note,snapshot) VALUES(?,?,?,?)",
                           (c["id"], status, str(feedback)[:2000], json.dumps(c, ensure_ascii=False)))

    def package(self, rid, cid, values):
        c = self.candidate_ids(rid, [cid])[0]
        if c["vod_id"] in self.service.active:
            raise ValueError("Aguarde a mineração terminar.")
        duration = self.store.get_vod(c["vod_id"])["duration"]
        start = number(values.get("recommended_start", c["start"]), 0, duration, "Início recomendado")
        end = number(values.get("recommended_end", c["end"]), start + 0.1, duration, "Fim recomendado")
        if end - start > 660:
            raise ValueError("Corte editorial deve ter até 11 minutos.")
        layout = values.get("layout", "")
        if layout not in ("", "VISUAL", "TALKING"):
            raise ValueError("Layout inválido.")
        package = {k: str(values.get(k, ""))[:2000] for k in ("title", "publication_title", "hook", "note")}
        package.update(recommended_start=start, recommended_end=end, layout=layout)
        with self.store.connect() as db:
            row = db.execute("SELECT data FROM candidates WHERE id=?", (cid,)).fetchone()
            data = json.loads(row[0])
            data["editorial_package"] = package
            db.execute("UPDATE candidates SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), cid))
        return package

    def cut_bounds(self, candidate, pre, post):
        package, suggestion = candidate.get("editorial_package", {}), candidate.get("editorial_review", {})
        cut = {**candidate, "start": package.get("recommended_start", suggestion.get("suggested_start", candidate["start"])),
               "end": package.get("recommended_end", suggestion.get("suggested_end", candidate["end"]))}
        return self.service.bounds(cut, pre, post)

    @performance.session()
    def export(self, cid, kind, pre, post, best, progress, check=lambda: None):
        began = time.perf_counter()
        c = self.store.candidate(cid)
        if kind == "raw" and c["status"] != "APROVADO":
            raise ValueError("Aprove o candidato antes de baixar o RAW.")
        vod = self.store.get_vod(c["vod_id"])
        package = c.get("editorial_package", {})
        suggestion = c.get("editorial_review", {})
        cut = {**c, "start": package.get("recommended_start", suggestion.get("suggested_start", c["start"])), "end": package.get("recommended_end", suggestion.get("suggested_end", c["end"]))}
        start, end = self.cut_bounds(c, pre, post)
        existing = self.store.rows("SELECT * FROM exports WHERE candidate_id=? AND kind=? AND start=? AND end=?", (cid, kind, start, end))
        if kind == "preview":
            existing = self.store.rows("SELECT * FROM exports WHERE vod_id=? AND kind='preview' AND start=? AND end=? ORDER BY id", (vod["id"], start, end))
        if existing and Path(existing[-1]["path"]).is_file():
            actual = media.probe(existing[-1]["path"])
            if best or kind == "preview" or (actual["height"] == 1080 and actual.get("fps", 0) >= 59):
                if kind == "preview":
                    Path(existing[-1]["path"]).touch()
                    self.store.update_vod(vod["id"], preview_metrics={"seconds": time.perf_counter()-began, "cache_hit": True})
                return "Arquivo já baixado; reutilizado."
        dirs = self.store.dirs(vod["campaign"], vod["id"])
        adapter = RemoteSource(vod, self.provider, self.temp, check, progress)
        lease, source = adapter.acquire(start, end, f"export:{cid}:{kind}", "preview" if kind == "preview" else "best" if best else "1080p60")
        check()
        info = json.loads((lease / "ready.json").read_text(encoding="utf-8"))
        if kind == "preview":
            self.previews.cleanup()
            target = self.previews.target(vod, start, end)
            progress(0, "Gerando Preview; cancelamento será aplicado ao concluir este trecho curto.")
            with performance.measure("preview_encode"):
                media.clip(source, target, 0, end - start, preview=True)
            self.previews.commit(target)
            check()
        else:
            folder = self.output / vod["campaign"].upper()
            folder.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(folder).free < source.stat().st_size + 512 * 1024**2:
                raise ValueError("Espaço insuficiente no destino do RAW. Temporário preservado para retry.")
            kind_label = package.get("layout") or c.get("type", "VISUAL")
            day = re.sub(r"[^0-9-]", "", vod.get("date") or "") or "SEM-DATA"
            name = f"{vod['campaign'].upper()}_{day}_{analysis.timestamp(cut['start']).replace(':', '')}_{kind_label}_{cid[:8]}_{uuid.uuid4().hex[:6]}_RAW.mp4"
            target = folder / name
            check()
            # Cross-volume copy remains in a unique, explicit partial file until complete.
            staging = target.with_suffix(".partial")
            try:
                shutil.copyfile(source, staging)
                staging.replace(target)
            finally:
                staging.unlink(missing_ok=True)
            analysis.save_json(target.with_suffix(".json"), {**info, "candidate_id": cid, "vod_id": vod["id"], "campaign": vod["campaign"], "editorial_package": package})
        self.store.execute("INSERT INTO exports(candidate_id,vod_id,kind,path,start,end) VALUES(?,?,?,?,?,?)", (cid, vod["id"], kind, str(target), start, end))
        checkpoint = dirs["candidates"] / f"export_{uuid.uuid4().hex[:12]}.json"
        analysis.save_json(checkpoint, {"path": str(target), "range": info, "candidate_id": cid})
        self.temp.commit(lease, checkpoint)
        actual = info["media"]
        if kind == "preview":
            self.store.update_vod(vod["id"], preview_metrics={"seconds": time.perf_counter()-began, "cache_hit": False, **performance.timings()})
        return f"{kind.upper()} pronto: {actual['width']}×{actual['height']} · {actual.get('fps', 0):.2f} fps. Range {analysis.timestamp(start)}–{analysis.timestamp(end)}."

    def enqueue(self, rid, kind, payload=None):
        self.get(rid)
        payload = payload or {}
        if kind not in ("sync", "manual", "mine", "raw", "preview", "editorial", "shortlist_previews", "backlog"):
            raise ValueError("Tarefa remota inválida.")
        if kind in ("sync", "mine", "manual", "editorial", "shortlist_previews", "backlog") and self.active(rid):
            raise ValueError("Aguarde ou cancele a tarefa desta campanha antes de iniciar outra.")
        jid = uuid.uuid4().hex
        self.store.execute("INSERT INTO remote_jobs(id,run_id,kind,state,payload,created) VALUES(?,?,?,'FILA',?,?)", (jid, rid, kind, json.dumps(payload), now()))
        def check():
            row = self.store.rows("SELECT cancel_requested FROM remote_jobs WHERE id=?", (jid,))[0]
            if row["cancel_requested"]:
                raise Cancelled()
        def progress(n, message):
            check()
            self.store.execute("UPDATE remote_jobs SET progress=?,message=? WHERE id=?", (round(n, 1), message[:1800], jid))
        def work():
            try:
                check()
                self.store.execute("UPDATE remote_jobs SET state='EXECUTANDO' WHERE id=?", (jid,))
                if kind == "sync":
                    result = self.sync(rid, check, progress)
                elif kind == "manual":
                    result = self.manual(rid, payload.get("urls", []), check, progress)
                elif kind == "mine":
                    result = self.mine(rid, payload, check, progress)
                elif kind == "backlog":
                    def pause_check():
                        rows = self.store.rows("SELECT pause_requested FROM remote_jobs WHERE id=?", (jid,))
                        return bool(rows and rows[0].get("pause_requested"))
                    result = backlog.run_backlog(self, rid, payload, check, progress, pause_check)
                elif kind == "editorial":
                    for vod in self.members(rid):
                        check()
                        editorial.review_vod(self.store, vod["id"], check)
                    result = "Revisor concluído usando somente os dados em cache. Sem mineração/download."
                elif kind == "shortlist_previews":
                    rows = [c for c in self.view(rid)["candidates"] if c.get("editorial_review", {}).get("classification") in ("RECOMENDADO", "BOM") and c["status"] != "DESCARTADO" and not c.get("refined_duplicate_of")]
                    errors = []
                    for c in rows:
                        check()
                        try:
                            self.export(c["id"], "preview", 0, 0, False, progress, check)
                        except Exception as exc:
                            errors.append(f"{c['id']}: {exc}")
                    if errors:
                        raise ValueError(" | ".join(errors)[:1800])
                    result = f"{len(rows)} previews da shortlist disponíveis; cache reutilizado."
                else:
                    c = self.candidate_ids(rid, [payload["candidate_id"]])[0]
                    result = self.export(c["id"], kind, payload.get("pre", 5), payload.get("post", 5), payload.get("best", False), progress, check)
                self.store.execute("UPDATE remote_jobs SET state='CONCLUÍDO',progress=100,message=? WHERE id=?", (result, jid))
            except Cancelled:
                self.store.execute("UPDATE remote_jobs SET state='CANCELADO',message='Cancelado com checkpoints preservados.' WHERE id=?", (jid,))
            except Exception as exc:
                self.store.execute("UPDATE remote_jobs SET state='ERRO',message=? WHERE id=?", (str(exc)[-1800:], jid))
        self.service.executor.submit(work)
        return jid

    def frame(self, vid, timestamp, progress):
        vod = self.store.get_vod(vid)
        start = min(timestamp, max(0, vod["duration"] - 5))
        end = min(start + 5, vod["duration"])
        adapter = RemoteSource(vod, self.provider, self.temp, progress=progress)
        lease, source = adapter.acquire(start, end, "frame", "best")
        folder = self.store.dirs(vod["campaign"], vid)["candidates"]
        target = folder / f"remote_frame_{timestamp:.3f}.jpg"
        media.frame(source, target, timestamp - start)
        info = media.probe(source)
        self.store.update_vod(vid, frame=str(target), width=info["width"], height=info["height"])
        proof = folder / f"remote_frame_{timestamp:.3f}.json"
        analysis.save_json(proof, {"frame": str(target), "timestamp": timestamp})
        self.temp.commit(lease, proof)
        return "Frame remoto disponível para configurar PREP."

    def cancel(self, rid):
        self.get(rid)
        self.store.execute("UPDATE remote_jobs SET cancel_requested=1 WHERE run_id=? AND state IN ('FILA','EXECUTANDO')", (rid,))

    def pause(self, rid):
        self.get(rid)
        self.store.execute(
            "UPDATE remote_jobs SET pause_requested=1 WHERE run_id=? AND kind='backlog' AND state IN ('FILA','EXECUTANDO')",
            (rid,)
        )

    def backlog_view(self, rid):
        running = self.store.rows("SELECT * FROM remote_jobs WHERE run_id=? AND kind='backlog' AND state IN ('FILA','EXECUTANDO')", (rid,))
        pause_req = bool(running and running[0].get("pause_requested"))
        return {
            "campaign": self.get(rid),
            "backlog": backlog.BacklogQueue(self, rid).load_queue(),
            "running_job": running[0] if running else None,
            "pause_requested": pause_req,
        }

    def retry_vod(self, rid, vid):
        self.get(rid)
        links = self.store.rows("SELECT * FROM remote_vods WHERE run_id=? AND vod_id=?", (rid, vid))
        if not links:
            raise ValueError("VOD não pertence a esta campanha operacional.")
        self.store.update_vod(vid, remote_state="PENDENTE", remote_error="")
        return {"ok": True, "vod_id": vid, "remote_state": "PENDENTE"}

    def download_approved(self, rid, ids, options):
        rows = self.candidate_ids(rid, ids)
        if any(c["status"] != "APROVADO" for c in rows):
            raise ValueError("Selecione somente candidatos aprovados.")
        queued = []
        for c in rows:
            active = self.store.rows("SELECT payload FROM remote_jobs WHERE run_id=? AND kind='raw' AND state IN ('FILA','EXECUTANDO')", (rid,))
            if any(json.loads(r["payload"]).get("candidate_id") == c["id"] for r in active):
                continue
            queued.append(self.enqueue(rid, "raw", {**options, "candidate_id": c["id"]}))
        return queued
