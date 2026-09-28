import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

target = '<input type="number" id="discoverLimit" min="1" max="100" value="50">'
replacement = target + '''
            </div>
            <div class="form-group" style="margin-top: 1rem;">
              <label>Cookies (Opcional - Cole o conteúdo do cookies.txt para bypass de Cloud)</label>
              <textarea id="discoverCookies" rows="3" placeholder="# Netscape HTTP Cookie File..."></textarea>
'''
html = html.replace(target, replacement)
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
