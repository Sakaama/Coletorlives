"""Backlog Runner module for continuous campaign VOD processing.

Processes discovered VODs in strict descending chronological order (newest to oldest),
dynamically prioritizing newly broadcast VODs, with safe pausing between VOD units,
failure isolation (one bad VOD does not halt the queue), persistent SQLite checkpoints,
and immediate shortlist availability upon completion of each VOD.
"""
from datetime import UTC, datetime
import logging


def date_of(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).date().isoformat()
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    return None


LOG = logging.getLogger(__name__)


def vod_timestamp_key(vod):
    """Return a sortable string representation of a VOD's live/recording date-time.
    
    Prefers date_time (ISO string), falling back to date, then created.
    """
    dt = vod.get("date_time")
    if dt:
        return str(dt)
    d = vod.get("date")
    if d:
        return f"{d}T00:00:00"
    created = vod.get("created")
    if created:
        return str(created).replace(" ", "T")
    return "1970-01-01T00:00:00"


def sort_backlog_vods(vods):
    """Sort VODs strictly from newest to oldest (date descending)."""
    return sorted(vods, key=vod_timestamp_key, reverse=True)


def filter_backlog_period(vods, min_date=None, max_date=None):
    """Filter VODs to only those within [min_date, max_date]."""
    filtered = []
    for v in vods:
        d = v.get("date")
        if not d and v.get("date_time"):
            d = date_of(v.get("date_time"))
        if not d:
            continue
        if min_date and d < min_date:
            continue
        if max_date and d > max_date:
            continue
        filtered.append(v)
    return filtered


def get_backlog_state(vod, candidates_count=0):
    """Determine operational backlog state for a VOD.
    
    States:
      - 'CONCLUÍDO' (Shortlist Ready / Finished)
      - 'EXECUTANDO' (Processing in progress)
      - 'ERRO' (Failed with error recorded)
      - 'BLOQUEADO' (Blocked by campaign eligibility rules)
      - 'PENDENTE' (Queued, waiting to be processed)
    """
    remote_state = vod.get("remote_state")
    if remote_state == "CONCLUÍDO" or (vod.get("analyzed") and candidates_count > 0):
        return "CONCLUÍDO"
    if remote_state == "EXECUTANDO":
        return "EXECUTANDO"
    if remote_state == "ERRO":
        return "ERRO"
    if remote_state == "BLOQUEADO" or vod.get("eligibility", {}).get("status") == "NÃO PERMITIDA":
        return "BLOQUEADO"
    return "PENDENTE"


class BacklogQueue:
    """Manages the prioritized backlog queue and status for an operational campaign."""

    def __init__(self, collector, rid):
        self.collector = collector
        self.rid = rid
        self.store = collector.store
        self.campaign_data = collector.get(rid)

    def load_queue(self):
        """Load and categorize all VODs in the backlog, sorted newest to oldest."""
        members = self.collector.members(self.rid)
        min_date = self.campaign_data.get("start")
        max_date = self.campaign_data.get("end")

        eligible = filter_backlog_period(members, min_date, max_date)
        sorted_vods = sort_backlog_vods(eligible)

        completed = []
        pending = []
        failed = []
        blocked = []
        processing = None
        shortlists_ready = 0
        candidates_waiting = 0

        for v in sorted_vods:
            cands = self.store.candidates(v["id"])
            c_count = len(cands)
            state = get_backlog_state(v, c_count)

            # Enrich VOD dictionary with backlog view properties
            entry = dict(v)
            entry["backlog_state"] = state
            entry["candidates_count"] = c_count

            # Count unreviewed candidates
            new_cands = sum(1 for c in cands if c.get("status") == "NOVO")
            candidates_waiting += new_cands

            if state == "CONCLUÍDO":
                completed.append(entry)
                shortlists_ready += 1
            elif state == "EXECUTANDO":
                processing = entry
            elif state == "ERRO":
                failed.append(entry)
            elif state == "BLOQUEADO":
                blocked.append(entry)
            else:
                pending.append(entry)

        return {
            "campaign": self.campaign_data,
            "total_found": len(sorted_vods),
            "completed_count": len(completed),
            "pending_count": len(pending),
            "failed_count": len(failed),
            "blocked_count": len(blocked),
            "shortlists_ready": shortlists_ready,
            "candidates_waiting": candidates_waiting,
            "processing": processing,
            "upcoming": pending,
            "failed": failed,
            "completed": completed,
        }


def run_backlog(collector, rid, options, check, progress, pause_check=lambda: False):
    """Execute the Backlog Runner loop for an operational campaign.
    
    Processes VODs one at a time in strict newest-to-oldest order.
    Dynamically re-evaluates the queue on each iteration so newly arrived VODs
    are immediately picked up at the head of the queue.
    Isolates per-VOD failures so the backlog continues to subsequent VODs.
    Honors pause requests safely after concluding the current VOD.
    """
    options = options or {}
    options.setdefault("mining_mode", "equilibrado")
    processed_count = 0
    errors = []

    LOG.info("Iniciando Backlog Runner para run_id=%s", rid)

    while True:
        check()
        if pause_check():
            LOG.info("Backlog Runner pausado pelo operador para run_id=%s", rid)
            return (
                f"Backlog pausado com segurança pelo operador. {processed_count} VOD(s) processada(s) nesta sessão. "
                "Retomada pronta."
            )

        # Reload queue dynamically to pick up any newly discovered VODs or retries
        queue_mgr = BacklogQueue(collector, rid)
        queue_data = queue_mgr.load_queue()
        pending = queue_data["upcoming"]

        if not pending:
            LOG.info("Backlog Runner concluído (nenhuma VOD pendente) para run_id=%s", rid)
            msg = f"Backlog concluído. {processed_count} VOD(s) processada(s)."
            if errors:
                msg += f" {len(errors)} VOD(s) com falha (consulte para retry)."
            return msg

        # Pick the newest pending VOD
        next_vod = pending[0]
        vid = next_vod["id"]
        v_title = next_vod.get("title", vid)
        v_date = next_vod.get("date", "data pendente")

        LOG.info("Backlog Runner processando VOD %s (%s, %s)", vid, v_date, v_title)
        progress(0, f"Iniciando VOD [{v_date}]: {v_title[:50]}…")

        with collector.service.lock:
            if vid in collector.service.active:
                # Already active in another thread
                LOG.warning("VOD %s já está em processamento ativo; pulando.", vid)
                continue
            collector.service.active.add(vid)

        try:
            collector.store.update_vod(vid, remote_state="EXECUTANDO")

            def vod_progress(pct, msg, v_date=v_date):
                check()
                progress(
                    pct,
                    f"VOD [{v_date}] ({pct:.0f}%): {msg}"
                )

            collector.analyze(vid, options, vod_progress, check)
            processed_count += 1
            collector.store.update_vod(vid, remote_state="CONCLUÍDO", remote_error="")
            LOG.info("VOD %s concluída com sucesso no backlog.", vid)
        except Exception as exc:
            # Check if it was an intentional cancellation
            from miner.remote_provider import Cancelled
            if isinstance(exc, Cancelled):
                collector.store.update_vod(vid, remote_state="PENDENTE", remote_error="Cancelado; checkpoints preservados.")
                raise
            # Failure isolation: record error on this VOD and continue backlog!
            err_msg = str(exc)
            LOG.error("Falha na VOD %s durante o backlog: %s", vid, err_msg)
            collector.store.update_vod(vid, remote_state="ERRO", remote_error=err_msg)
            errors.append(f"{vid} ({v_date}): {err_msg[:80]}")
        finally:
            with collector.service.lock:
                collector.service.active.discard(vid)
