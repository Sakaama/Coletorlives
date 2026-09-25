import datetime
import logging
import json
import os
import secrets
import sys
import threading
import uuid
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request, send_file, session
from werkzeug.exceptions import HTTPException

from miner import analysis, media, editorial
from miner.auth import (
    ROLE_EDITOR,
    get_current_user,
    get_user_store,
    is_auth_required,
    require_role,
    verify_radar_secret,
)
from miner.cloud_db import get_firestore_service
from miner.collector import Collector
from miner.errors import present_job
from miner.presentation import PresentationService
from miner.service import Service, number
from miner.storage import get_storage_service
from miner.telegram import get_telegram_service

ROOT = Path(__file__).resolve().parent


def create_app(data=None):
    app = Flask(__name__)
    app.config.update(JSON_AS_ASCII=False)
    app.json.ensure_ascii = False
    service = Service(ROOT, data)
    app.extensions["miner"] = service
    token = secrets.token_urlsafe(32)
    configured_secret = os.environ.get("SECRET_KEY", "").strip()
    if is_auth_required() and not configured_secret:
        raise RuntimeError(
            "Configuração inválida: AUTH_REQUIRED=true exige que SECRET_KEY seja fornecida externamente no ambiente."
        )
    app.secret_key = configured_secret or token
    store = service.store
    collector = Collector(service)
    app.extensions["collector"] = collector
    presentation = PresentationService(service, collector)
    app.extensions["presentation"] = presentation

    # Unified Storage, Cloud Firestore, and Telegram Services
    storage_svc = get_storage_service(ROOT)
    cloud_db = get_firestore_service()
    telegram_svc = get_telegram_service()
    user_store = get_user_store(reload=True)
    app.extensions["storage"] = storage_svc
    app.extensions["cloud_db"] = cloud_db
    app.extensions["telegram"] = telegram_svc
    app.extensions["user_store"] = user_store

    @app.before_request
    def check_access():
        # 1. Exempt webhook and validate via radar secret / token
        if request.path == "/api/webhook/radar":
            if not verify_radar_secret():
                return jsonify(error="Acesso não autorizado: token ou segredo do webhook inválido."), 401
            return None

        # 2. Check remote IP unless ALLOW_REMOTE or AUTH_REQUIRED is enabled
        allow_remote = (
            os.environ.get("ALLOW_REMOTE", "false").lower() in ("1", "true", "yes")
            or is_auth_required()
        )
        if not allow_remote and request.remote_addr not in ("127.0.0.1", "::1", None):
            return jsonify(error="O aplicativo aceita somente conexões locais."), 403

        # 3. Check CSRF / Session token on modifying requests
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.path in ("/api/auth/login", "/api/auth/logout"):
                return None

            hdr_token = request.headers.get("X-Miner-Token", "")
            has_valid_token = bool(hdr_token and secrets.compare_digest(hdr_token, token))
            has_valid_session = bool(session.get("user") and session["user"].get("authenticated") is not False)

            if not has_valid_token and not has_valid_session and not allow_remote:
                return jsonify(error="Recarregue a página para renovar a sessão local."), 403

            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                return jsonify(error="Origem não permitida."), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
        return response

    @app.errorhandler(Exception)
    def failure(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, (ValueError, FileNotFoundError)):
            return jsonify(error=str(exc)), 400
        app.logger.exception("Erro na requisição")
        return jsonify(error="Falha inesperada. Consulte logs/miner.log; os dados foram preservados."), 500

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            token=token,
            user=get_current_user(),
            auth_required=is_auth_required(),
        )

    @app.get("/api/state")
    def state():
        vods = [
            store.get_vod(r["id"])
            for r in store.rows("SELECT id FROM vods ORDER BY created DESC, rowid DESC")
        ]
        return jsonify(
            campaigns=service.campaigns,
            vods=vods,
            jobs=[
                present_job(job)
                for job in store.rows("SELECT * FROM jobs ORDER BY created DESC, rowid DESC LIMIT 100")
            ],
        )

    @app.get("/api/health")
    def health():
        return jsonify(
            ok=True,
            ffmpeg=media.binary("ffmpeg"),
            ffprobe=media.binary("ffprobe"),
            hardware=analysis.hardware(),
            data=str(store.root),
            cloud={
                "storage_mode": storage_svc.mode,
                "storage_bucket": getattr(storage_svc, "bucket_name", None),
                "firestore_connected": cloud_db.is_connected,
                "telegram_configured": telegram_svc.is_configured,
                "auth_required": is_auth_required(),
            },
            user=get_current_user(),
        )

    @app.get("/api/product/dashboard")
    def product_dashboard():
        return jsonify(presentation.get_dashboard())

    @app.get("/api/product/creators")
    def product_creators():
        return jsonify(creators=presentation.get_creators())

    @app.get("/api/product/inbox")
    def product_inbox():
        return jsonify(
            presentation.get_inbox(
                campaign_id=request.args.get("campaign"),
                creator=request.args.get("creator"),
                status=request.args.get("status"),
                classification=request.args.get("classification"),
                search=request.args.get("search"),
                limit=int(request.args.get("limit", 150)),
                offset=int(request.args.get("offset", 0)),
            )
        )

    @app.get("/api/product/vods")
    def product_vods():
        return jsonify(
            vods=presentation.get_vods(
                creator=request.args.get("creator"),
                status=request.args.get("status"),
                search=request.args.get("search"),
            )
        )

    @app.get("/api/product/creator/<key>/workspace")
    def product_creator_workspace(key):
        return jsonify(presentation.get_creator_workspace(key))

    @app.post("/api/product/caption/generate")
    def product_generate_caption():
        body = request.get_json() or {}
        cid = body.get("candidate_id")
        if not cid:
            raise ValueError("candidate_id é obrigatório.")
        platform = body.get("platform", "TikTok")
        seed = int(body.get("variation_seed", 0))
        return jsonify(presentation.get_caption_package(cid, platform=platform, variation_seed=seed))

    @app.get("/api/remote/campaigns")
    def remote_campaigns():
        return jsonify(campaigns=[collector.get(r["id"]) for r in store.rows("SELECT id FROM remote_campaigns ORDER BY rowid DESC")])

    @app.post("/api/remote/campaigns")
    def configure_remote():
        body = request.get_json()
        return jsonify(campaign=collector.configure(body, body.get("id")))

    @app.get("/api/remote/<rid>")
    def remote_detail(rid):
        return jsonify(collector.view(rid))

    @app.get("/api/remote/<rid>/backlog")
    def remote_backlog(rid):
        return jsonify(collector.backlog_view(rid))

    @app.post("/api/remote/<rid>/action")
    def remote_action(rid):
        body = request.get_json()
        kind = body.get("kind")
        if kind == "pause":
            collector.pause(rid)
            return jsonify(ok=True)
        if kind == "retry_vod":
            return jsonify(collector.retry_vod(rid, body.get("vod_id")))
        if kind == "cancel":
            collector.cancel(rid)
            return jsonify(ok=True)
        if kind == "review":
            collector.review(rid, body.get("ids", []), body.get("status"), body.get("feedback", ""))
            return jsonify(ok=True)
        if kind == "package":
            return jsonify(package=collector.package(rid, body.get("candidate_id"), body.get("values", {})))
        if kind == "download":
            return jsonify(jobs=collector.download_approved(rid, body.get("ids", []), {
                "pre": number(body.get("pre", 5), 0, 120, "Pré-roll"),
                "post": number(body.get("post", 5), 0, 120, "Pós-roll"), "best": bool(body.get("best"))}))
        if kind == "retry":
            jobs = store.rows("SELECT * FROM remote_jobs WHERE id=? AND run_id=?", (body.get("job"), rid))
            if not jobs or jobs[0]["state"] not in ("ERRO", "CANCELADO", "INTERROMPIDO"):
                raise ValueError("Tarefa não disponível para retry.")
            import json
            payload = json.loads(jobs[0]["payload"])
            if body.get("best"):
                payload["best"] = True
            return jsonify(job=collector.enqueue(rid, jobs[0]["kind"], payload))
        if kind == "manual":
            urls = body.get("urls", [])
            if not isinstance(urls, list) or not 1 <= len(urls) <= 20:
                raise ValueError("Inclua de 1 a 20 URLs por vez.")
            from miner.rules import validate_url
            body["urls"] = list(dict.fromkeys(validate_url(url)[1] for url in urls))
        if kind == "preview":
            candidate = collector.candidate_ids(rid, [body.get("candidate_id")])[0]
            start, end = collector.cut_bounds(candidate, body.get("pre", 0), body.get("post", 0))
            cached = store.rows("SELECT * FROM exports WHERE vod_id=? AND kind='preview' AND start=? AND end=? ORDER BY id DESC", (candidate["vod_id"], start, end))
            if cached and Path(cached[0]["path"]).is_file():
                Path(cached[0]["path"]).touch()
                return jsonify(export=cached[0], cached=True)
            body.setdefault("pre", 0)
            body.setdefault("post", 0)
        return jsonify(job=collector.enqueue(rid, kind, body))

    @app.post("/api/discover")
    def discover():
        body = request.get_json() or {}
        campaign = body.get("campaign")
        if not campaign:
            raise ValueError("Selecione uma campanha.")
        url = body.get("url", "")
        if not url:
            raise ValueError("Informe a URL do canal, playlist ou vídeo do YouTube.")
        limit = body.get("limit", 50)
        return jsonify(service.discover(campaign, url, limit))

    @app.post("/api/import/url")
    def import_url():
        body = request.get_json()
        return jsonify(service.import_url(body.get("campaign"), body.get("url", "")))

    @app.post("/api/import/local")
    def import_local():
        body = request.get_json()
        existing = body.get("existing")
        if existing:
            vod = store.get_vod(existing)
            if existing in service.active or vod.get("local_path"):
                raise ValueError(
                    "Esta VOD já possui arquivo ou processamento ativo. Importe como uma nova VOD."
                )
        return jsonify(
            service.import_local(
                body.get("campaign"), body.get("path", ""), body.get("title"), body.get("date"), existing
            )
        )

    @app.post("/api/pick-file")
    def pick_file():
        # Native dialog returns a path, avoiding upload/copy of multi-hour videos.
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "pick_file.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=media.FLAGS,
        )
        if result.returncode:
            raise ValueError("Seletor de arquivos indisponível. Cole o caminho completo no campo.")
        return jsonify(path=result.stdout.strip())

    @app.get("/api/vods/<vid>")
    def detail(vid):
        return jsonify(
            vod=store.get_vod(vid),
            candidates=editorial.group_refined(store.candidates(vid, include_archived=request.args.get("history") == "1")),
        )

    @app.post("/api/vods/<vid>/action")
    def action(vid):
        body = request.get_json()
        kind = body.get("kind")
        vod = store.get_vod(vid)
        if kind == "metadata":

            def work(p):
                return service.metadata(vid, p)
        elif kind == "download":
            if vod.get("remote") and not vod.get("local_path"):
                raise ValueError("Remote Mode usa somente ranges. Use Garimpar pendentes, Preview ou Baixar aprovados.")
            if not vod.get("url"):
                raise ValueError("Esta VOD é um arquivo local.")
            if not vod.get("duration"):
                raise ValueError("Obtenha os metadados antes de baixar.")
            if vod.get("eligibility", {}).get("status") != "PERMITIDA" and not body.get("reviewed"):
                raise ValueError("Confira as regras e marque que revisou os avisos antes de baixar.")
            store.update_vod(vid, download_warnings_acknowledged=True)

            def work(p):
                return service.download(vid, p)
        elif kind == "analyze":

            def work(p):
                if vod.get("remote") and not vod.get("local_path"):
                    return collector.analyze(vid, body, p)
                return service.analyze(vid, body, p)
        elif kind in ("raw", "prep", "preview"):
            ids = list(dict.fromkeys(body.get("ids", [])))
            if not ids or len(ids) > 500:
                raise ValueError("Selecione de 1 a 500 candidatos.")
            for cid in ids:
                if store.candidate(cid)["vod_id"] != vid:
                    raise ValueError("Candidato não pertence a esta VOD.")
            pre = number(body.get("pre", 5), 0, 120, "Pré-roll")
            post = number(body.get("post", 5), 0, 120, "Pós-roll")

            def work(p):
                if vod.get("remote") and not vod.get("local_path") and kind in ("raw", "preview"):
                    return " ".join(collector.export(cid, kind, pre, post, bool(body.get("best")), p) for cid in ids)
                if body.get("remote_raw") and kind == "raw":
                    return service.export(vid, ids, kind, pre, post, p, remote=body["remote_raw"])
                return service.export(vid, ids, kind, pre, post, p)
        elif kind == "frame":
            if not vod.get("local_path") and not vod.get("remote"):
                raise ValueError("Importe ou baixe o vídeo primeiro.")
            timestamp = number(body.get("time", 0), 0, max(0, vod["duration"] - 0.1), "Tempo do frame")

            def work(p):
                if vod.get("remote") and not vod.get("local_path"):
                    return collector.frame(vid, timestamp, p)
                target = store.dirs(vod["campaign"], vid)["candidates"] / f"frame_{timestamp:.2f}.jpg"
                media.frame(vod["local_path"], target, timestamp)
                store.update_vod(vid, frame=str(target))
                return "Frame disponível. Arraste sobre a imagem para selecionar a região."
        else:
            raise ValueError("Ação desconhecida.")
        return jsonify(job=service.submit(vid, kind, work))

    @app.post("/api/vods/<vid>/review")
    def review(vid):
        body = request.get_json()
        status = body.get("status")
        if status not in ("NOVO", "APROVADO", "DESCARTADO"):
            raise ValueError("Status inválido.")
        if vid in service.active:
            raise ValueError("Aguarde a tarefa da VOD terminar antes de alterar a revisão.")
        ids = body.get("ids", [])
        with store.connect() as db:
            for cid in ids:
                candidate = store.candidate(cid)
                if candidate["vod_id"] != vid:
                    raise ValueError("Candidato não pertence à VOD.")
                db.execute("UPDATE candidates SET status=? WHERE id=? AND vod_id=?", (status, cid, vid))
                db.execute("INSERT INTO editorial_feedback(candidate_id,status,note,snapshot) VALUES(?,?,?,?)", (cid, status, str(body.get("feedback", ""))[:2000], json.dumps(candidate, ensure_ascii=False)))
        return jsonify(ok=True)

    @app.post("/api/vods/<vid>/regions")
    def regions(vid):
        vod, body = store.get_vod(vid), request.get_json()
        if not vod.get("width"):
            raise ValueError("Importe ou baixe o vídeo primeiro.")
        camera = media.validate_rect(body.get("camera"), vod["width"], vod["height"])
        content = media.validate_rect(body.get("content"), vod["width"], vod["height"])
        x = int(number(body.get("text_x", 35), 0, 1000, "Posição X do texto"))
        y = int(number(body.get("text_y", 680), 0, 1860, "Posição Y do texto"))
        store.update_vod(vid, camera=camera, content=content, vertical={"text_x": x, "text_y": y})
        return jsonify(ok=True)

    @app.get("/media/frame/<vid>")
    def vod_frame(vid):
        path = store.get_vod(vid).get("frame")
        if not path or not Path(path).is_file():
            raise ValueError("Gere um frame primeiro.")
        return send_file(path, conditional=True)

    @app.get("/media/export/<int:eid>")
    def exported(eid):
        rows = store.rows("SELECT path FROM exports WHERE id=?", (eid,))
        if not rows or not Path(rows[0]["path"]).is_file():
            raise ValueError("Arquivo não encontrado.")
        return send_file(rows[0]["path"], conditional=True, as_attachment=request.args.get("download") == "1")

    # =========================================================================
    # UNIFIED CLOUD, AUTH, WEBHOOK, EDITING & TELEGRAM ROUTES
    # =========================================================================

    @app.get("/api/product/cloud-status")
    def product_cloud_status():
        return jsonify(
            storage_mode=storage_svc.mode,
            storage_bucket=getattr(storage_svc, "bucket_name", None),
            firestore_connected=cloud_db.is_connected,
            telegram_configured=telegram_svc.is_configured,
            auth_required=is_auth_required(),
            current_user=get_current_user(),
        )

    @app.post("/api/auth/login")
    def auth_login():
        body = request.get_json() or {}
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        user = user_store.authenticate(username, password)
        if not user:
            return jsonify(error="Usuário ou senha inválidos.", code=401), 401
        session["user"] = user
        return jsonify(ok=True, user=user)

    @app.post("/api/auth/logout")
    def auth_logout():
        session.pop("user", None)
        return jsonify(ok=True)

    @app.get("/api/auth/me")
    def auth_me():
        return jsonify(user=get_current_user(), auth_required=is_auth_required())

    @app.post("/api/webhook/radar")
    def webhook_radar():
        body = request.get_json() or {}
        channel = (body.get("channel") or body.get("creator") or "gabepeixe").lower().strip()
        platform = str(body.get("platform") or "twitch").lower().strip()
        category = str(body.get("category") or "Geral").strip()
        hook = str(body.get("hook") or body.get("title") or "Momento detectado pelo Radar").strip()
        context = str(body.get("context") or body.get("summary") or "").strip()
        start = float(body.get("start", 0.0))
        end = float(body.get("end", max(30.0, start + 45.0)))
        score = float(body.get("score", 85.0))
        clip_id = str(body.get("id") or uuid.uuid4())

        # Ensure radar parent VOD exists in SQLite
        radar_vod_id = f"radar_{channel}"
        vod_data = json.dumps({
            "title": f"Radar: {channel.title()} ({platform.upper()})",
            "url": body.get("url", f"https://{platform}.tv/{channel}"),
            "broadcast_date": datetime.date.today().isoformat(),
            "provider": platform.title(),
            "creator": channel,
            "status": "Radar",
        }, ensure_ascii=False)

        today_str = datetime.date.today().isoformat()
        with store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO vods (id, campaign, source_key, data, created) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (radar_vod_id, channel, f"radar_{today_str}", vod_data),
            )
            cand_data = json.dumps({
                "source": "radar",
                "platform": platform,
                "channel": channel,
                "category": category,
                "summary": context or hook,
                "reason": f"Alerta automático emitido pelo Radar {platform.upper()}",
                "editorial_review": {
                    "hook": hook,
                    "title": hook,
                    "classification": "RECOMENDADO" if score >= 80 else "BOM",
                    "editorial_score": score,
                    "reason": context or f"Alerta emitido pelo Radar de {platform.upper()}",
                    "suggested_start": start,
                    "suggested_end": end,
                },
            }, ensure_ascii=False)
            db.execute(
                "INSERT OR REPLACE INTO candidates (id, vod_id, start, end, score, status, data) VALUES (?, ?, ?, ?, ?, 'NOVO', ?)",
                (clip_id, radar_vod_id, start, end, score, cand_data),
            )

        # Sync to Firestore if configured
        if cloud_db.is_connected:
            cloud_db.sync_radar_clip({
                "id": clip_id,
                "channel": channel,
                "platform": platform,
                "category": category,
                "hook": hook,
                "context": context,
                "start": start,
                "end": end,
                "score": score,
            })

        return jsonify(status="success", id=clip_id, channel=channel), 201

    @app.post("/api/product/clip/<cid>/upload-edited")
    @require_role(ROLE_EDITOR)
    def upload_edited_clip(cid):
        # Query raw JSON to preserve all fields
        with store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT data FROM candidates WHERE id=?", (cid,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Candidato '{cid}' não encontrado.")
            data = json.loads(row[0]) if row[0] else {}

        if "video" not in request.files:
            raise ValueError("Nenhum arquivo de vídeo enviado (campo 'video').")

        file = request.files["video"]
        if not file.filename:
            raise ValueError("Arquivo de vídeo sem nome.")

        notes = request.form.get("notes", "").strip()
        title = request.form.get("title", "").strip()
        sync_telegram = request.form.get("sync_telegram", "false").lower() in ("1", "true", "yes")

        # Save to storage (GCS private blob or Local private storage)
        stored = storage_svc.save_edited_video(
            candidate_id=cid,
            file_obj=file.stream,
            filename=file.filename,
        )

        edited_info = {
            "url": stored["url"],
            "path": stored.get("path") or stored.get("blob_name"),
            "filename": stored["filename"],
            "storage_mode": stored["storage_mode"],
            "notes": notes,
            "title": title or data.get("title") or "Vídeo Editado",
            "uploaded_at": datetime.datetime.now().isoformat(),
        }
        data["edited_video"] = edited_info

        with store.connect() as db:
            db.execute(
                "UPDATE candidates SET status='PRONTO_PARA_POSTAR', data=? WHERE id=?",
                (json.dumps(data, ensure_ascii=False), cid),
            )
            db.execute(
                "INSERT INTO editorial_feedback (candidate_id, status, note, snapshot) VALUES (?, 'PRONTO_PARA_POSTAR', ?, ?)",
                (cid, f"Vídeo editado enviado: {file.filename}. {notes}".strip(), json.dumps(data, ensure_ascii=False)),
            )

        # Sync to Firestore if connected
        if cloud_db.is_connected:
            cloud_db.sync_edited_clip({
                "id": cid,
                "title": edited_info["title"],
                "notes": notes,
                "video_url": stored["url"],
                "blob_name": stored.get("blob_name"),
            })

        telegram_res = None
        if sync_telegram and telegram_svc.is_configured:
            cand = store.candidate(cid)
            caption_pkg = None
            try:
                caption_pkg = presentation.get_caption_package(cid)
            except Exception:
                pass
            tg_caption = telegram_svc.format_publication_caption(cand, caption_pkg)
            video_target = stored["path"] if stored["storage_mode"] == "local" else stored["url"]
            telegram_res = telegram_svc.send_video(video_target, caption=tg_caption)

        return jsonify(
            ok=True,
            candidate_id=cid,
            edited_video=edited_info,
            status="PRONTO_PARA_POSTAR",
            telegram=telegram_res,
        )

    @app.post("/api/product/clip/<cid>/send-telegram")
    @require_role(ROLE_EDITOR)
    def clip_send_telegram(cid):
        cand = store.candidate(cid)
        if not cand:
            raise ValueError(f"Candidato '{cid}' não encontrado.")

        if not telegram_svc.is_configured:
            raise ValueError("Telegram não está configurado (defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID).")

        edited_video = cand.get("edited_video")
        video_target = None
        if edited_video:
            if edited_video.get("storage_mode") == "local" and edited_video.get("path"):
                video_target = edited_video["path"]
            else:
                video_target = edited_video.get("url")

        # Fallback to preview export if no edited video uploaded
        if not video_target:
            rows = store.rows(
                "SELECT path FROM exports WHERE candidate_id=? AND kind='preview' ORDER BY id DESC",
                (cid,),
            )
            if rows and Path(rows[0]["path"]).is_file():
                video_target = rows[0]["path"]

        caption_pkg = None
        try:
            caption_pkg = presentation.get_caption_package(cid)
        except Exception:
            pass

        caption_text = telegram_svc.format_publication_caption(cand, caption_pkg)

        if video_target:
            res = telegram_svc.send_video(video_target, caption=caption_text)
        else:
            res = telegram_svc.send_message(caption_text)

        if not res.get("ok"):
            raise ValueError(f"Falha ao enviar para o Telegram: {res.get('error')}")

        return jsonify(ok=True, result=res)

    @app.get("/media/edited/<path:filename>")
    def media_edited(filename):
        edited_dir = ROOT / "data" / "edited"
        target = (edited_dir / filename).resolve()
        # Path traversal guard
        if not str(target).startswith(str(edited_dir.resolve())) or not target.is_file():
            raise ValueError("Arquivo editado não encontrado.")
        return send_file(str(target), conditional=True)

    return app


if __name__ == "__main__":
    from waitress import serve
    from miner.instance import acquire

    instance = acquire(ROOT / "data" / ".instance.lock")
    if instance is None:
        print("O TUTUCO CLIP MINER já está aberto em http://127.0.0.1:8765")
        if "--no-browser" not in sys.argv:
            webbrowser.open("http://127.0.0.1:8765")
        sys.exit(0)
    (ROOT / "logs").mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        ROOT / "logs" / "miner.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
    app = create_app()
    print("TUTUCO CLIP MINER - http://127.0.0.1:8765\nMantenha esta janela aberta. Ctrl+C para encerrar.")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    serve(app, host="127.0.0.1", port=8765, threads=6)
