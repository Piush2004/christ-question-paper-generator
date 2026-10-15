
import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar
import re

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(url)
opener.open(url).read()

params = urllib.parse.urlencode({'where': 'Undergraduate', 'keyword': 'Bachelor of Computer Applications', 'sem': '1 Semester'})
res_url = 'http://databank.christuniversity.in/out1.php?' + params
resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
with open('scratch/res.html', 'w', encoding='utf-8') as f:
    f.write(resp)
print('Saved to res.html')
