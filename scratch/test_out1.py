import urllib.request
import urllib.parse

import re

url = 'http://databank.christuniversity.in/out1.php'
data = urllib.parse.urlencode({
    'where': '1',
    'keyword': 'Bachelor',
    'sem': '1',
    'submit': 'Search'
}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers={
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'application/x-www-form-urlencoded'
})
# wait, out1.php might be a GET request. The previous URL was GET.
# Let's try GET first.
url_get = url + '?' + urllib.parse.urlencode({
    'where': '1',
    'keyword': 'Bachelor',
    'sem': '1',
    'submit': 'Search'
})
try:
    with urllib.request.urlopen(url_get) as response:
        html = response.read().decode('utf-8')
    print('GET response length:', len(html))
    if 'No Files Found' in html:
        print('GET: No Files Found')
    else:
        links = re.findall(r'<a href="([^"]+\.dat)">', html)
        print('GET found links:', len(links))
except Exception as e:
    print('GET error:', e)
