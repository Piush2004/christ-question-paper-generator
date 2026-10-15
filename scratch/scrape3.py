import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar
import re

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(url)
opener.open(url).read()

params = urllib.parse.urlencode({'keyword': 'BCA', 'where': 'All words'})
res_url = 'http://databank.christuniversity.in/out.php?' + params
print('Fetching:', res_url)
resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
print('Length:', len(resp))
links = re.findall(r'<a href=[\'\"\s]?(odm_data/\d+\.dat)[\'\"\s]?>', resp, re.IGNORECASE)
print('Found links:', len(links))
if links:
    print('First 5:', links[:5])
