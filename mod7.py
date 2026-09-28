import re
with open('miner/leitura.py', 'r', encoding='utf-8') as f:
    py = f.read()

target = '''            '--dump-json',
            '--extractor-args', 'youtube:player_client=android',

            '-o', os.path.join(tmpdir, '%(id)s.%(ext)s'),'''
            
replacement = '''            '--dump-json',
            '-o', os.path.join(tmpdir, '%(id)s.%(ext)s'),'''

py = py.replace(target, replacement)

with open('miner/leitura.py', 'w', encoding='utf-8') as f:
    f.write(py)
