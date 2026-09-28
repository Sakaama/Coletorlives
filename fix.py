import re
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(
    r'<div id=\"user-role-pill\".*?>',
    '<div id=\"user-role-pill\" class=\"badge badge-accent\" style=\"font-size:11px; padding:4px 8px; cursor:pointer;\" title=\"Clique para logar\" onclick=\"doLogin()\">',
    html
)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
