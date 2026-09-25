from pathlib import Path

collector_path = Path("miner/collector.py")
content = collector_path.read_text(encoding="utf-8")
is_crlf = "\r\n" in content
content = content.replace("\r\n", "\n")

# 1. pause_requested migration
idx = content.find("UPDATE remote_jobs SET state='INTERROMPIDO'")
assert idx != -1, "update statement not found"
end_idx = content.find("self.temp.cleanup()", idx)
assert end_idx != -1, "cleanup not found"

injection = """UPDATE remote_jobs SET state='INTERROMPIDO',message='Reinicie a ação para retomar checkpoints.'
                  WHERE state IN ('FILA','EXECUTANDO');
            \"\"\"
            try:
                db.execute("ALTER TABLE remote_jobs ADD COLUMN pause_requested INTEGER DEFAULT 0")
            except Exception:
                pass
        """
content = content[:idx] + injection + content[end_idx:]

# 2. members sorted by backlog.sort_backlog_vods
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

# 3. enqueue support for backlog
content = content.replace(
    'if kind not in ("sync", "manual", "mine", "raw", "preview", "editorial", "shortlist_previews"):',
    'if kind not in ("sync", "manual", "mine", "raw", "preview", "editorial", "shortlist_previews", "backlog"):'
)
content = content.replace(
    'if kind in ("sync", "mine", "manual", "editorial", "shortlist_previews") and self.active(rid):',
    'if kind in ("sync", "mine", "manual", "editorial", "shortlist_previews", "backlog") and self.active(rid):'
)

# 4. work dispatch for backlog
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

# 5. Add pause, backlog_view, retry_vod
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

if is_crlf:
    content = content.replace("\n", "\r\n")

collector_path.write_text(content, encoding="utf-8")
print("Updated miner/collector.py successfully!")
