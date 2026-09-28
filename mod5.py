import re
with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

target = 'const res = await api(\'/api/discover\', { campaign, url, limit });'
replacement = '''
    const cookiesNode = document.getElementById('discoverCookies');
    const cookies = cookiesNode ? cookiesNode.value.trim() : "";
    const res = await api('/api/discover', { campaign, url, limit, cookies });
'''
js = js.replace(target, replacement)

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(js)
