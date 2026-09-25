from pathlib import Path

collector_path = Path("miner/collector.py")
content = collector_path.read_text(encoding="utf-8")

# 1. Imports
content = content.replace(
    "from miner import analysis, long_vod, media, editorial, performance",
    "from miner import analysis, backlog, editorial, long_vod, media, performance"
)

# 2. Add pause_requested migration in __init__
idx = content.find("UPDATE remote_jobs SET state='INTERROMPIDO'")
assert idx != -1, "UPDATE remote_jobs not found"
end_marker = '            """)\n        self.temp.cleanup()'
end_idx = content.find(end_marker, idx)
assert end_idx != -1, "end_marker not found"

new_init_tail = """            \"\"\"
            try:
                db.execute("ALTER TABLE remote_jobs ADD COLUMN pause_requested INTEGER DEFAULT 0")
            except Exception:
                pass
        self.temp.cleanup()"""

content = content[:end_idx] + new_init_tail + content[end_idx + len(end_marker):]

# 3. members sorted by backlog.sort_backlog_vods
m_idx = content.find("def members(self, rid):")
assert m_idx != -1, "members not found"
m_end = content.find("def view(self, rid):", m_idx)
assert m_end != -1, "view not found"

new_members = """def members(self, rid):
        run = self.get(rid)
        vods = [self.store.get_vod(r["vod_id"]) for r in self.store.rows("SELECT vod_id FROM remote_vods WHERE run_id=?", (rid,))]
        filtered = [v for v in vods if not v.get("date") or run["start"] <= v["date"] <= run["end"]]
        return backlog.sort_backlog_vods(filtered)

    """
content = content[:m_idx] + new_members + content[m_end:]

# 4. enqueue support for backlog
content = content.replace(
    'if kind not in ("sync", "manual", "mine", "raw", "preview", "editorial", "shortlist_previews"):',
    'if kind not in ("sync", "manual", "mine", "raw", "preview", "editorial", "shortlist_previews", "backlog"):'
)
content = content.replace(
    'if kind in ("sync", "mine", "manual", "editorial", "shortlist_previews") and self.active(rid):',
    'if kind in ("sync", "mine", "manual", "editorial", "shortlist_previews", "backlog") and self.active(rid):'
)

# 5. work dispatch for backlog
k_idx = content.find('elif kind == "mine":')
assert k_idx != -1, "mine not found"
k_end = content.find('elif kind == "editorial":', k_idx)
assert k_end != -1, "editorial not found"

new_dispatch = """elif kind == "mine":
                    result = self.mine(rid, payload, check, progress)
                elif kind == "backlog":
                    def pause_check():
                        rows = self.store.rows("SELECT pause_requested FROM remote_jobs WHERE id=?", (jid,))
                        return bool(rows and rows[0].get("pause_requested"))
                    result = backlog.run_backlog(self, rid, payload, check, progress, pause_check)
                """
content = content[:k_idx] + new_dispatch + content[k_end:]

# 6. Add pause, backlog_view, retry_vod
c_idx = content.find("def cancel(self, rid):")
assert c_idx != -1, "cancel not found"
c_end = content.find("def download_approved(self, rid, ids, options):", c_idx)
assert c_end != -1, "download_approved not found"

new_cancel_block = """def cancel(self, rid):
        self.get(rid)
        self.store.execute("UPDATE remote_jobs SET cancel_requested=1 WHERE run_id=? AND state IN ('FILA','EXECUTANDO')", (rid,))

    def pause(self, rid):
        self.get(rid)
        self.store.execute(
            "UPDATE remote_jobs SET pause_requested=1 WHERE run_id=? AND kind='backlog' AND state IN ('FILA','EXECUTANDO')",
            (rid,)
        )

    def backlog_view(self, rid):
        return backlog.BacklogQueue(self, rid).load_queue()

    def retry_vod(self, rid, vid):
        self.get(rid)
        links = self.store.rows("SELECT * FROM remote_vods WHERE run_id=? AND vod_id=?", (rid, vid))
        if not links:
            raise ValueError("VOD não pertence a esta campanha operacional.")
        self.store.update_vod(vid, remote_state="PENDENTE", remote_error="")
        return {"ok": True, "vod_id": vid, "remote_state": "PENDENTE"}

    """
content = content[:c_idx] + new_cancel_block + content[c_end:]

collector_path.write_text(content, encoding="utf-8", newline="\n")
print("Updated miner/collector.py successfully!")
