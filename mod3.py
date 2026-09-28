import re
with open('app.py', 'r', encoding='utf-8') as f:
    app = f.read()

target = '''        from miner.leitura import leitura_expressa
        try:
            return jsonify(leitura_expressa(url, campaign))'''
replacement = '''        cookies_txt = body.get("cookies", "")
        from miner.leitura import leitura_expressa
        try:
            return jsonify(leitura_expressa(url, campaign, cookies_txt=cookies_txt))'''
app = app.replace(target, replacement)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app)
