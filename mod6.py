import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

target = r'<div class="fields"><label>Limite de v.deos \(1 a 100\)<input id="discover-limit" type="number" min="1" max="100" value="50"></label></div>'

def replacer(match):
    return match.group(0) + '''
          <div class="fields" style="margin-top: 1rem;">
            <label>Cookies (Opcional - Cole o conteúdo do cookies.txt para bypass de bloqueio)<textarea id="discoverCookies" rows="3" placeholder="# Netscape HTTP Cookie File..."></textarea></label>
          </div>
'''

html = re.sub(target, replacer, html)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
