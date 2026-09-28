import re
with open('miner/leitura.py', 'r', encoding='utf-8') as f:
    py = f.read()

target = "raise Exception('yt-dlp failed (android client): ' + res.stderr)"
replacement = "raise Exception('yt-dlp failed: ' + res.stderr)"
py = py.replace(target, replacement)

with open('miner/leitura.py', 'w', encoding='utf-8') as f:
    f.write(py)
