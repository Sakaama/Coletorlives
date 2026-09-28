import re
with open('static/product.js', 'r', encoding='utf-8') as f:
    js = f.read()

target = 'const limit = parseInt(document.getElementById(\'discoverLimit\').value, 10) || 50;'
replacement = target + '''
    const cookiesNode = document.getElementById('discoverCookies');
    const cookies = cookiesNode ? cookiesNode.value.trim() : "";
'''
js = js.replace(target, replacement)

target2 = 'body: JSON.stringify({ campaign: currentCampaign, url, limit })'
replacement2 = 'body: JSON.stringify({ campaign: currentCampaign, url, limit, cookies })'
js = js.replace(target2, replacement2)

with open('static/product.js', 'w', encoding='utf-8') as f:
    f.write(js)
