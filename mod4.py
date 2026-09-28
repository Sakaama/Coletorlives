import re
with open('miner/leitura.py', 'r', encoding='utf-8') as f:
    py = f.read()

target = 'def get_subtitles(url):'
replacement = 'def get_subtitles(url, cookies_txt=""): '
py = py.replace(target, replacement)

target2 = '''            '--dump-json',
            '--extractor-args', 'youtube:player_client=android','''
replacement2 = '''            '--dump-json',
            '--extractor-args', 'youtube:player_client=android',
'''
py = py.replace(target2, replacement2)

target3 = '''            '-o', os.path.join(tmpdir, '%(id)s.%(ext)s'),
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)'''

replacement3 = '''            '-o', os.path.join(tmpdir, '%(id)s.%(ext)s'),
            url
        ]
        if cookies_txt:
            cookie_path = os.path.join(tmpdir, 'cookies.txt')
            with open(cookie_path, 'w', encoding='utf-8') as cf:
                cf.write(cookies_txt)
            cmd.insert(1, '--cookies')
            cmd.insert(2, cookie_path)
            
        res = subprocess.run(cmd, capture_output=True, text=True)'''

py = py.replace(target3, replacement3)

target4 = 'def leitura_expressa(url, campaign="GabePeixe"):'
replacement4 = 'def leitura_expressa(url, campaign="GabePeixe", cookies_txt=""):'
py = py.replace(target4, replacement4)

target5 = 'source_title, vod_id, text = get_subtitles(url)'
replacement5 = 'source_title, vod_id, text = get_subtitles(url, cookies_txt)'
py = py.replace(target5, replacement5)

with open('miner/leitura.py', 'w', encoding='utf-8') as f:
    f.write(py)
