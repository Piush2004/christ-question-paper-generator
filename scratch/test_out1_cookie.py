import urllib.request
import urllib.parse
import http.cookiejar
import re

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
urllib.request.install_opener(opener)

login_url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(login_url)

url_get = 'http://databank.christuniversity.in/out1.php?' + urllib.parse.urlencode({
    'where': '1',
    'keyword': 'Bachelor',
    'sem': '1',
    'submit': 'Search'
})

response = opener.open(url_get)
html = response.read().decode('utf-8')
print('GET response length:', len(html))
if 'No Files Found' in html:
    print('GET: No Files Found')
else:
    links = re.findall(r'<a href="([^"]+\.dat)">', html)
    print('GET found links:', len(links))
    if links:
        print(f"Sample link: {links[0]}")
