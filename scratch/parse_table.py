import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open('http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in')
url = 'http://databank.christuniversity.in/out1.php?' + urllib.parse.urlencode({'where': '1', 'keyword': 'Bachelor', 'sem': '1', 'submit': 'Search'})
res = opener.open(url)
html = res.read().decode('utf-8')

rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
for i, row in enumerate(rows):
    cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
    cols = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip() for c in cols]
    
    links = re.findall(r'href=["\']?([^"\'>]+)["\']?', row, re.IGNORECASE)
    link = links[0] if links else 'no link'
    
    # We only care about rows that contain 'BCA' or 'Bachelor of Computer Applications'
    if 'BCA' in ' '.join(cols) or 'Computer Applications' in ' '.join(cols) or i < 3:
        print(' | '.join(cols), '->', link)
