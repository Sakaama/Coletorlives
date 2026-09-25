from pathlib import Path

app_path = Path("app.py")
text = app_path.read_text(encoding="utf-8").replace("\r\n", "\n")

idx = text.find('@app.get("/api/remote/<rid>")')
assert idx != -1, "route not found"

action_idx = text.find('if kind == "cancel":', idx)
assert action_idx != -1, "action_idx not found"

# 1. Insert @app.get("/api/remote/<rid>/backlog") right before @app.post("/api/remote/<rid>/action")
post_idx = text.find('@app.post("/api/remote/<rid>/action")', idx)
assert post_idx != -1, "post_idx not found"

backlog_endpoint = """    @app.get("/api/remote/<rid>/backlog")
    def remote_backlog(rid):
        return jsonify(collector.backlog_view(rid))

"""
text = text[:post_idx] + backlog_endpoint + text[post_idx:]

# 2. Insert pause and retry_vod in remote_action
cancel_idx = text.find('if kind == "cancel":')
assert cancel_idx != -1, "cancel_idx not found"

action_handlers = """if kind == "pause":
            collector.pause(rid)
            return jsonify(ok=True)
        if kind == "retry_vod":
            return jsonify(collector.retry_vod(rid, body.get("vod_id")))
        """
text = text[:cancel_idx] + action_handlers + text[cancel_idx:]

app_path.write_text(text, encoding="utf-8", newline="\n")
print("app.py updated successfully!")
