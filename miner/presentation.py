"""Presentation Layer for TUTUCO Clip Miner.

Provides safe, read-only aggregation and human-centric view models
for the Dashboard, Campaigns, Creators, Sources/VODs, and Clip Inbox.
Does not alter pipeline behavior, database tables, or mining logic.
"""
import json


def format_duration(seconds: float | int | None) -> str:
    """Format duration in seconds to human-readable string (e.g. '12h 21m' or '45s')."""
    if not seconds or seconds <= 0:
        return "0s"
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m" if minutes > 0 else f"{hours}h"
    if minutes > 0:
        return f"{minutes}m {sec:02d}s" if sec > 0 else f"{minutes}m"
    return f"{sec}s"


def format_timestamp(seconds: float | int | None) -> str:
    """Format seconds into HH:MM:SS format."""
    if seconds is None:
        return "00:00:00"
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    sec = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"


def get_creator_meta(creator_key: str) -> dict:
    """Return presentation metadata for known creators.
    
    Adheres strictly to factual data: visual template specs from TUTUCO-TV/08_TEMPLATES
    and honest behavioral states ('Perfil comportamental em construção através da análise das lives')
    without manufactured or fake psychographic adjectives.
    """
    key = (creator_key or "").lower().strip()
    creators = {
        "gabepeixe": {
            "name": "GabePeixe",
            "handle": "@gabepeixe",
            "platforms": ["Kick"],
            "avatar": "🐟",
            "color": "#10B981",
            "category": "Gaming & React",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
                "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
                "lower_text": "kick.com/gabepeixe",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Momentos de Gameplay", "Reações / Destaques"],
                "topics": ["Minecraft", "TCG / Coringa", "FC 27", "Presencial Narizes"],
                "typical_duration": "30s a 65s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
        "brkk": {
            "name": "BRKK",
            "handle": "@brkk",
            "platforms": ["YouTube", "Kick"],
            "avatar": "⚡",
            "color": "#F59E0B",
            "category": "Competitivo & Gameplay",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
                "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
                "lower_text": "kick.com/brkk",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Clutches & Jogadas", "Highlights Competitivos"],
                "topics": ["Valorant", "Competitivo", "Ranked"],
                "typical_duration": "20s a 45s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
        "brabox": {
            "name": "BRABOX",
            "handle": "@brabox",
            "platforms": ["Twitch"],
            "avatar": "🥊",
            "color": "#6366F1",
            "category": "Entretenimento & Variedades",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
                "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
                "lower_text": "twitch.tv/brabox",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Momentos Engraçados", "Interação"],
                "topics": ["Variedades", "Conversa", "Jogos Casuais"],
                "typical_duration": "35s a 60s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
        "joaopichau": {
            "name": "João Pichau",
            "handle": "@joaopichau",
            "platforms": ["YouTube"],
            "avatar": "🖥️",
            "color": "#EC4899",
            "category": "Hardware & Tech",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
                "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
                "lower_text": "youtube.com/@joaopichau",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Dicas de Hardware", "Benchmarks"],
                "topics": ["PC Gamer", "Hardware", "Custo-Benefício"],
                "typical_duration": "40s a 80s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
        "juninhomanella": {
            "name": "Juninho Manella",
            "handle": "@juninhomanella",
            "platforms": ["YouTube"],
            "avatar": "⚽",
            "color": "#3B82F6",
            "category": "Futebol & Desafios",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo/Gameplay embaixo",
                "layout_talking": "B-Roll/Foto em cima + Câmera embaixo",
                "lower_text": "youtube.com/@juninhomanella",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Desafios", "Gols & Lances"],
                "topics": ["Futebol", "Desafios", "X1"],
                "typical_duration": "25s a 50s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
    }
    return creators.get(
        key,
        {
            "name": creator_key.title() if creator_key else "Criador",
            "handle": f"@{key}" if key else "@criador",
            "platforms": ["Kick"],
            "avatar": "🎬",
            "color": "#8B5CF6",
            "category": "Criador de Conteúdo",
            "template_layout": {
                "canvas": "1080x1920 (9:16 vertical)",
                "fps": 30,
                "layout_visual": "Câmera em cima + Conteúdo embaixo",
                "layout_talking": "B-Roll em cima + Câmera embaixo",
                "lower_text": f"@{key}" if key else "",
                "destinations": ["TikTok", "Instagram Reels", "YouTube Shorts", "Kwai"],
            },
            "dna": {
                "tone": "Perfil comportamental em construção através da análise das lives",
                "formats": ["Momentos Gerais"],
                "topics": ["Lives"],
                "typical_duration": "30s a 60s",
                "speech_pattern": "Padrão de fala em calibração automática",
                "status": "Perfil comportamental em construção através da análise das lives",
            },
        },
    )


class PresentationService:
    """Aggregates and formats data for product views."""

    def __init__(self, service, collector):
        self.service = service
        self.collector = collector
        self.store = service.store

    def get_dashboard(self) -> dict:
        """Return comprehensive operational metrics for the Dashboard."""
        with self.store.connect() as db:
            # Basic counts
            cur = db.cursor()
            cur.execute("SELECT count(*) FROM candidates")
            total_candidates = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM candidates WHERE status='APROVADO'")
            approved_candidates = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM candidates WHERE status='DESCARTADO'")
            discarded_candidates = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM candidates WHERE status='NOVO'")
            new_candidates = cur.fetchone()[0]

            # Remote campaigns
            cur.execute("SELECT count(*) FROM remote_campaigns")
            campaigns_count = cur.fetchone()[0]

            # VODs breakdown
            cur.execute("SELECT id, campaign, data FROM vods")
            vod_rows = cur.fetchall()

        total_vods = len(vod_rows)
        completed_vods = 0
        pending_vods = 0
        processing_vods = 0
        failed_vods = 0
        total_duration_sec = 0.0
        analyzed_duration_sec = 0.0
        creators_set = set()

        for _vid, camp, data_str in vod_rows:
            d = json.loads(data_str) if data_str else {}
            creator = camp or d.get("creator") or d.get("streamer")
            if creator:
                creators_set.add(creator.lower())

            dur = d.get("duration") or 0.0
            total_duration_sec += dur

            rstate = d.get("remote_state")
            analyzed = d.get("analyzed")

            # Check candidate count for completion heuristic
            if rstate == "CONCLUÍDO" or (analyzed and not rstate):
                completed_vods += 1
                analyzed_duration_sec += dur
            elif rstate == "EXECUTANDO":
                processing_vods += 1
            elif rstate == "ERRO":
                failed_vods += 1
            else:
                pending_vods += 1

        # Check active jobs for real processing card
        active_job_info = None
        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute(
                "SELECT id, run_id, kind, state, progress, message, created FROM remote_jobs "
                "WHERE state='EXECUTANDO' ORDER BY created DESC LIMIT 1"
            )
            job_row = cur.fetchone()
            if job_row:
                active_job_info = {
                    "id": job_row[0],
                    "run_id": job_row[1],
                    "kind": job_row[2],
                    "state": job_row[3],
                    "progress": job_row[4],
                    "message": job_row[5],
                    "created": job_row[6],
                }

        # Recent activity
        activity = []
        with self.store.connect() as db:
            cur = db.cursor()
            # Recent reviews
            cur.execute(
                "SELECT candidate_id, status, note, created FROM editorial_feedback "
                "ORDER BY created DESC LIMIT 10"
            )
            for cid, status, note, created in cur.fetchall():
                badge_type = "success" if status == "APROVADO" else "danger" if status == "DESCARTADO" else "neutral"
                activity.append({
                    "id": f"rev_{cid}_{created}",
                    "type": "review",
                    "badge": status,
                    "badge_type": badge_type,
                    "title": f"Clip {cid[:8]} marcado como {status}",
                    "detail": note if note else "Revisão editorial",
                    "timestamp": created,
                })

            # Recent jobs
            cur.execute(
                "SELECT id, kind, state, message, created FROM remote_jobs "
                "ORDER BY created DESC LIMIT 10"
            )
            for jid, kind, state, msg, created in cur.fetchall():
                badge_type = "success" if state == "CONCLUÍDO" else "danger" if state in ("ERRO", "CANCELADO") else "accent"
                activity.append({
                    "id": f"job_{jid}_{created}",
                    "type": "job",
                    "badge": state,
                    "badge_type": badge_type,
                    "title": f"Tarefa {kind.upper()}: {state}",
                    "detail": msg or "",
                    "timestamp": created,
                })

        # Sort activity by timestamp descending
        activity.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
        recent_activity = activity[:15]

        return {
            "metrics": {
                "campaigns_count": max(campaigns_count, 1),
                "creators_count": max(len(creators_set), 1),
                "vods_total": total_vods,
                "vods_completed": completed_vods,
                "vods_pending": pending_vods,
                "vods_processing": processing_vods,
                "vods_failed": failed_vods,
                "hours_analyzed": round(analyzed_duration_sec / 3600, 1),
                "hours_analyzed_formatted": format_duration(analyzed_duration_sec),
                "total_duration_formatted": format_duration(total_duration_sec),
                "total_candidates": total_candidates,
                "approved_candidates": approved_candidates,
                "new_candidates": new_candidates,
                "discarded_candidates": discarded_candidates,
                "shortlist_candidates": approved_candidates + sum(
                    1 for r in self._get_shortlist_candidates()
                ),
            },
            "active_processing": active_job_info,
            "recent_activity": recent_activity,
        }

    def _get_shortlist_candidates(self) -> list:
        """Helper to count shortlist candidates quickly."""
        shortlist = []
        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT id, data FROM candidates WHERE status != 'DESCARTADO'")
            for cid, data_str in cur.fetchall():
                d = json.loads(data_str) if data_str else {}
                er = d.get("editorial_review", {})
                if er.get("classification") in ("RECOMENDADO", "BOM"):
                    shortlist.append(cid)
        return shortlist

    def get_creators(self) -> list:
        """Return list of creators with operational stats and DNA profile."""
        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT id, campaign, data FROM vods")
            vod_rows = cur.fetchall()

            # Candidates per vod
            cur.execute("SELECT vod_id, count(*), sum(case when status='APROVADO' then 1 else 0 end) FROM candidates GROUP BY vod_id")
            cand_stats = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        creators_map = {}
        # Prepopulate known creators
        for key in ["gabepeixe", "brkk", "brabox", "joaopichau", "juninhomanella"]:
            creators_map[key] = {
                "key": key,
                **get_creator_meta(key),
                "vods_count": 0,
                "vods_completed": 0,
                "hours_analyzed_sec": 0.0,
                "candidates_count": 0,
                "approved_count": 0,
                "campaigns": [],
            }

        for vid, camp, data_str in vod_rows:
            d = json.loads(data_str) if data_str else {}
            key = (camp or d.get("creator") or "gabepeixe").lower()
            if key not in creators_map:
                creators_map[key] = {
                    "key": key,
                    **get_creator_meta(key),
                    "vods_count": 0,
                    "vods_completed": 0,
                    "hours_analyzed_sec": 0.0,
                    "candidates_count": 0,
                    "approved_count": 0,
                    "campaigns": [],
                }

            c = creators_map[key]
            c["vods_count"] += 1
            dur = d.get("duration") or 0.0
            if d.get("remote_state") == "CONCLUÍDO" or d.get("analyzed"):
                c["vods_completed"] += 1
                c["hours_analyzed_sec"] += dur

            cands, apps = cand_stats.get(vid, (0, 0))
            c["candidates_count"] += cands
            c["approved_count"] += apps

        result = []
        for _key, c in creators_map.items():
            c["hours_analyzed_formatted"] = format_duration(c["hours_analyzed_sec"])
            c["hours_analyzed"] = round(c["hours_analyzed_sec"] / 3600, 1)
            result.append(c)

        # Sort with creators having most candidates first
        result.sort(key=lambda x: (x["candidates_count"], x["vods_count"]), reverse=True)
        return result

    def get_inbox(
        self,
        campaign_id: str = None,
        creator: str = None,
        status: str = None,
        classification: str = None,
        search: str = None,
        limit: int = 150,
        offset: int = 0,
    ) -> dict:
        """Return enriched candidates for the Clip Inbox."""
        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT id, campaign, data FROM vods")
            vod_lookup = {}
            for vid, camp, d_str in cur.fetchall():
                d = json.loads(d_str) if d_str else {}
                vod_lookup[vid] = {
                    "campaign": camp or "gabepeixe",
                    "title": d.get("title") or vid,
                    "date": str(d.get("broadcast_date") or d.get("date") or "")[:10],
                    "url": d.get("url") or "",
                    "provider": "Kick" if "kick.com" in (d.get("url") or "") else "YouTube" if "youtube.com" in (d.get("url") or "") else "Local",
                }

            # Exports lookup for fast preview/raw indicator
            cur.execute("SELECT candidate_id, kind, id FROM exports")
            exports_lookup = {}
            for cid, kind, eid in cur.fetchall():
                exports_lookup.setdefault(cid, []).append({"kind": kind, "export_id": eid})

            # Fetch candidates
            query = "SELECT id, vod_id, start, end, score, status, data FROM candidates"
            rows = cur.execute(query).fetchall()

        items = []
        counts = {
            "total": len(rows),
            "NOVO": 0,
            "APROVADO": 0,
            "PRONTO_PARA_POSTAR": 0,
            "DESCARTADO": 0,
            "RECOMENDADO": 0,
            "BOM": 0,
            "TALVEZ": 0,
            "FRACO": 0,
            "SHORTLIST": 0,
        }

        search_lower = (search or "").lower().strip()

        for cid, vid, start, end, raw_score, c_status, data_str in rows:
            d = json.loads(data_str) if data_str else {}
            v_info = vod_lookup.get(vid, {"campaign": "gabepeixe", "title": vid, "date": "", "provider": "Local"})
            c_creator = v_info["campaign"].lower()

            er = d.get("editorial_review") or {}
            c_class = er.get("classification") or ("RECOMENDADO" if raw_score >= 82 else "BOM" if raw_score >= 68 else "TALVEZ" if raw_score >= 48 else "FRACO")
            editorial_score = er.get("editorial_score") or raw_score

            # Update count tallies
            if c_status in counts:
                counts[c_status] += 1
            if c_class in counts:
                counts[c_class] += 1
            if c_class in ("RECOMENDADO", "BOM") and c_status != "DESCARTADO":
                counts["SHORTLIST"] += 1

            # Filter logic
            if status and status != "ALL" and c_status != status:
                continue
            if creator and creator.lower() != c_creator:
                continue
            if classification and classification != "TODOS":
                if classification == "SHORTLIST":
                    if c_class not in ("RECOMENDADO", "BOM") or c_status == "DESCARTADO":
                        continue
                elif c_class != classification:
                    continue

            # Text search filter
            summary = d.get("summary") or ""
            hook = er.get("hook") or ""
            title = er.get("title") or ""
            reason = er.get("reason") or d.get("reason") or ""
            if search_lower:
                text_corpus = f"{summary} {hook} {title} {reason} {v_info['title']} {cid}".lower()
                if search_lower not in text_corpus:
                    continue

            # Duration and timestamps
            duration_sec = round(max(0.1, end - start), 1)
            suggested_start = er.get("suggested_start")
            suggested_end = er.get("suggested_end")

            human_title = title or summary or f"Momento em {format_timestamp(start)}"
            creator_meta = get_creator_meta(c_creator)

            items.append({
                "id": cid,
                "vod_id": vid,
                "vod_title": v_info["title"],
                "vod_date": v_info["date"],
                "provider": v_info["provider"],
                "creator": creator_meta["name"],
                "creator_avatar": creator_meta["avatar"],
                "creator_key": c_creator,
                "start": start,
                "end": end,
                "start_formatted": format_timestamp(start),
                "end_formatted": format_timestamp(end),
                "suggested_start_formatted": format_timestamp(suggested_start) if suggested_start is not None else None,
                "suggested_end_formatted": format_timestamp(suggested_end) if suggested_end is not None else None,
                "duration_sec": duration_sec,
                "duration_formatted": f"{int(duration_sec)}s",
                "score": int(editorial_score),
                "raw_score": int(raw_score),
                "classification": c_class,
                "status": c_status,
                "title": human_title,
                "hook": hook or None,
                "summary": summary,
                "reason": reason,
                "visual_activity": d.get("visual_activity_level") or "MEDIUM",
                "content_type": er.get("content_type") or d.get("type") or "GAMEPLAY",
                "exports": exports_lookup.get(cid, []),
                "transcript": summary or (d.get("text") or ""),
                "edited_video": d.get("edited_video"),
            })

        # Sort items: Recommended first, then score descending, then date
        class_rank = {"RECOMENDADO": 0, "BOM": 1, "TALVEZ": 2, "FRACO": 3}
        items.sort(key=lambda x: (class_rank.get(x["classification"], 4), -x["score"]))

        paged_items = items[offset : offset + limit]

        return {
            "items": paged_items,
            "total_matches": len(items),
            "counts": counts,
            "limit": limit,
            "offset": offset,
        }

    def get_vods(self, creator: str = None, status: str = None, search: str = None) -> list:
        """Return list of all VODs with human presentation details."""
        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT id, campaign, source_key, created, data FROM vods ORDER BY created DESC, rowid DESC")
            vod_rows = cur.fetchall()

            sql_stats = (
                "SELECT vod_id, count(*), "
                "sum(case when score >= 68 then 1 else 0 end), "
                "sum(case when status = 'APROVADO' then 1 else 0 end) "
                "FROM candidates GROUP BY vod_id"
            )
            cur.execute(sql_stats)
            stats = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}

        result = []
        search_lower = (search or "").lower().strip()

        for vid, camp, skey, _created, data_str in vod_rows:
            d = json.loads(data_str) if data_str else {}
            c_creator = (camp or d.get("creator") or "gabepeixe").lower()

            if creator and creator.lower() != c_creator:
                continue

            v_title = d.get("title") or vid
            if search_lower and search_lower not in v_title.lower() and search_lower not in vid.lower():
                continue

            rstate = d.get("remote_state")
            analyzed = d.get("analyzed")
            c_count, sl_count, ap_count = stats.get(vid, (0, 0, 0))

            # Operational status mapping (supports Portuguese operational terms)
            if rstate == "CONCLUÍDO" or (analyzed and c_count > 0):
                human_status = "Analisado"
                status_key = "processed"
                status_color = "success"
            elif rstate == "EXECUTANDO":
                human_status = "Processando"
                status_key = "processing"
                status_color = "accent"
            elif rstate == "ERRO":
                human_status = "Erro"
                status_key = "failed"
                status_color = "danger"
            elif rstate == "BLOQUEADO" or d.get("eligibility", {}).get("status") == "NÃO PERMITIDA":
                human_status = "Bloqueado"
                status_key = "blocked"
                status_color = "warning"
            else:
                human_status = "Na Fila" if d.get("url") else "Descoberto"
                status_key = "queued" if d.get("url") else "discovered"
                status_color = "neutral"

            if status:
                st_clean = status.lower().strip()
                if st_clean not in (human_status.lower(), status_key.lower()):
                    continue

            dur = d.get("duration") or 0.0
            v_date = str(d.get("broadcast_date") or d.get("date") or skey or "")[:10]
            url = d.get("url") or ""
            platform = "Kick" if "kick.com" in url else "YouTube" if "youtube.com" in url else "Twitch" if "twitch.tv" in url else "Local"
            creator_meta = get_creator_meta(c_creator)

            result.append({
                "id": vid,
                "title": v_title,
                "creator": creator_meta["name"],
                "creator_avatar": creator_meta["avatar"],
                "creator_key": c_creator,
                "date": v_date,
                "duration": dur,
                "duration_formatted": format_duration(dur),
                "platform": platform,
                "status": human_status,
                "status_key": status_key,
                "status_color": status_color,
                "candidates_count": c_count,
                "shortlist_count": sl_count,
                "approved_count": ap_count,
                "error": d.get("remote_error") or "",
                "url": url,
                "has_local_media": bool(d.get("local_path")),
            })

        # Sort by date descending
        result.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
        return result

    def get_creator_workspace(self, creator_key: str) -> dict:
        """Return dedicated workspace data for a specific creator.
        
        Includes creator meta, campaign rules, template specs, VODs, candidates,
        and honest Perfil de Cortes.
        """
        key = (creator_key or "").lower().strip()
        creator_meta = get_creator_meta(key)

        from miner.caption import load_campaign_config, load_creator_template

        campaign_cfg = load_campaign_config(self.store.root, key)
        template_cfg = load_creator_template(self.store.root, key)

        vods = self.get_vods(creator=key)
        inbox = self.get_inbox(creator=key, limit=50)

        vods_count = len(vods)
        completed_vods = sum(1 for v in vods if v.get("status") in ("Analisado", "Processed"))
        total_cand = sum(v.get("candidates_count", 0) for v in vods)
        total_shortlist = sum(v.get("shortlist_count", 0) for v in vods)
        total_approved = sum(v.get("approved_count", 0) for v in vods)
        hours_sec = sum(v.get("duration", 0) for v in vods if v.get("status") in ("Analisado", "Processed"))

        stats = {
            "vods_count": vods_count,
            "vods_completed": completed_vods,
            "candidates_count": total_cand,
            "shortlist_count": total_shortlist,
            "approved_count": total_approved,
            "hours_analyzed": round(hours_sec / 3600, 1),
            "hours_analyzed_formatted": format_duration(hours_sec),
        }

        # Calculate average duration of candidate clips if any
        items = inbox.get("items", [])
        avg_dur = round(sum(it.get("duration_sec", 0) for it in items) / len(items), 1) if items else 45.0

        perfil_de_cortes = {
            "status": "Perfil comportamental em construção através da análise das lives",
            "canvas": template_cfg.get("canvas"),
            "fps": template_cfg.get("fps"),
            "editing_software": template_cfg.get("editing_software"),
            "destinations": template_cfg.get("destinations"),
            "layout_visual": template_cfg.get("layout_visual"),
            "layout_talking": template_cfg.get("layout_talking"),
            "lower_text": campaign_cfg.get("vertical", {}).get("text") or f"kick.com/{key}",
            "subtitle_rule": template_cfg.get("subtitle_rule"),
            "average_clip_duration": f"{avg_dur}s",
            "sample_candidates_analyzed": total_cand,
            "approved_cuts": total_approved,
            "formats_detected": creator_meta.get("dna", {}).get("formats", ["Momentos Gerais"]),
            "topics": creator_meta.get("dna", {}).get("topics", []),
        }

        return {
            "creator": {
                "key": key,
                **creator_meta,
                **stats,
            },
            "campaign": campaign_cfg,
            "template": template_cfg,
            "stats": stats,
            "vods": vods,
            "recent_candidates": items,
            "perfil_de_cortes": perfil_de_cortes,
        }

    def get_caption_package(
        self, candidate_id: str, platform: str = "TikTok", variation_seed: int = 0
    ) -> dict:
        """Generate publication package for a candidate clip with deterministic campaign rules."""
        from miner.caption import CaptionGenerator, load_campaign_config

        with self.store.connect() as db:
            cur = db.cursor()
            cur.execute("SELECT id, vod_id, start, end, score, status, data FROM candidates WHERE id=?", (candidate_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Candidato '{candidate_id}' não encontrado.")

            cid, vid, start, end, score, status, data_str = row
            data = json.loads(data_str) if data_str else {}

            cur.execute("SELECT campaign, data FROM vods WHERE id=?", (vid,))
            v_row = cur.fetchone()
            camp = "gabepeixe"
            v_title = vid
            if v_row:
                camp = v_row[0] or "gabepeixe"
                vd = json.loads(v_row[1]) if v_row[1] else {}
                v_title = vd.get("title") or vid

        candidate_payload = {
            "id": cid,
            "vod_id": vid,
            "vod_title": v_title,
            "creator_key": camp,
            "start": start,
            "end": end,
            "duration": end - start,
            "score": score,
            "status": status,
            "title": data.get("editorial_review", {}).get("title") or data.get("title") or v_title,
            "hook": data.get("editorial_review", {}).get("hook") or data.get("hook"),
            "summary": data.get("summary") or data.get("reason"),
            "transcript": data.get("text") or data.get("transcript") or data.get("summary") or "",
            "edited_video": data.get("edited_video"),
        }

        camp_cfg = load_campaign_config(self.store.root, camp)
        gen = CaptionGenerator(self.store.root)
        return gen.generate(
            candidate_payload,
            campaign=camp_cfg,
            platform=platform,
            variation_seed=variation_seed,
        )
