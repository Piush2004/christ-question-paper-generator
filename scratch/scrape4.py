import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(url)
opener.open(url).read()

params = urllib.parse.urlencode({'keyword': 'BCA101', 'where': 'All words'})
res_url = 'http://databank.christuniversity.in/out.php?' + params
print('Fetching:', res_url)
resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
with open('scratch/res2.html', 'w', encoding='utf-8') as f:
    f.write(resp)
print('Saved to res2.html, len:', len(resp))
