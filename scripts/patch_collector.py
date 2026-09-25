from pathlib import Path

collector_path = Path("miner/collector.py")
content = collector_path.read_text(encoding="utf-8")
is_crlf = "\r\n" in content
content = content.replace("\r\n", "\n")

# 1. Add backlog to imports
content = content.replace(
    "from miner import analysis, long_vod, media, editorial, performance",
    "from miner import analysis, backlog, editorial, long_vod, media, performance"
)

# 2. Add pause_requested migration in __init__
old_init = "                UPDATE remote_jobs SET state='INTERROMPIDO',message='Reinicie a ação para retomar checkpoints.'\n                  WHERE state IN ('FILA','EXECUTANDO');\n            \")\"\""
old_init = old_init.replace('")"""', '""")')
new_init = old_init + '\n            try:\n                db.execute("ALTER TABLE remote_jobs ADD COLUMN pause_requested INTEGER DEFAULT 0")\n            except Exception:\n                pass'

assert old_init in content, "old_init not found"
content = content.replace(old_init, new_init, 1)

# 3. members sorted by backlog.sort_backlog_vods
old_members = """    def members(self, rid):
        run = self.get(rid)
        vods = [self.store.get_vod(r["vod_id"]) for r in self.store.rows("SELECT vod_id FROM remote_vods WHERE run_id=?", (rid,))]
        return [v for v in vods if not v.get("date") or run["start"] <= v["date"] <= run["end"]]"""

new_members = """    def members(self, rid):
        run = self.get(rid)
        vods = [self.store.get_vod(r["vod_id"]) for r in self.store.rows("SELECT vod_id FROM remote_vods WHERE run_id=?", (rid,))]
        filtered = [v for v in vods if not v.get("date") or run["start"] <= v["date"] <= run["end"]]
        return backlog.sort_backlog_vods(filtered)"""

assert old_members in content, "old_members not found"
content = content.replace(old_members, new_members, 1)

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
old_mine = """                elif kind == "mine":
                    result = self.mine(rid, payload, check, progress)"""
new_mine = """                elif kind == "mine":
                    result = self.mine(rid, payload, check, progress)
                elif kind == "backlog":
                    def pause_check():
                        rows = self.store.rows("SELECT pause_requested FROM remote_jobs WHERE id=?", (jid,))
                        return bool(rows and rows[0].get("pause_requested"))
                    result = backlog.run_backlog(self, rid, payload, check, progress, pause_check)"""
assert old_mine in content, "old_mine not found"
content = content.replace(old_mine, new_mine, 1)

# 6. Add pause, backlog_view, retry_vod
old_cancel = """    def cancel(self, rid):
        self.get(rid)
        self.store.execute("UPDATE remote_jobs SET cancel_requested=1 WHERE run_id=? AND state IN ('FILA','EXECUTANDO')", (rid,))"""

new_cancel = """    def cancel(self, rid):
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
        return {"ok": True, "vod_id": vid, "remote_state": "PENDENTE"}"""

assert old_cancel in content, "old_cancel not found"
content = content.replace(old_cancel, new_cancel, 1)

if is_crlf:
    content = content.replace("\n", "\r\n")

collector_path.write_text(content, encoding="utf-8")
print("Patch applied to miner/collector.py successfully!")
