import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar
import re
import os
import time

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(url)
opener.open(url).read()

# Let's see what values 'sem' accepts by extracting it
html = opener.open(url).read().decode('utf-8', errors='ignore')
forms = re.findall(r'(<form.*?</form>)', html, re.DOTALL | re.IGNORECASE)
f0 = forms[0]
sems = []
for m in re.finditer(r'<option value=[\'\"]?(.*?)[\'\"]?>(.*?)</option>', f0):
    if 'Semester' in m.group(2) or 'Trimester' in m.group(2):
        sems.append(m.group(1))

print("Found sems:", sems[:10])

# Just test for 1 Semester
params = urllib.parse.urlencode({'where': 'Undergraduate', 'keyword': 'Bachelor of Computer Applications', 'sem': '1 Semester'})
res_url = 'http://databank.christuniversity.in/out1.php?' + params
print('Fetching:', res_url)
resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
print('Results length:', len(resp))
links = re.findall(r'<a href=[\'\"\s]?(odm_data/\d+\.dat)[\'\"\s]?>', resp, re.IGNORECASE)
print('Found', len(links), 'links for 1 Semester')
if links:
    print('First 5:', links[:5])

# Also check for 4 Semester
params = urllib.parse.urlencode({'where': 'Undergraduate', 'keyword': 'Bachelor of Computer Applications', 'sem': '4 Semester'})
res_url = 'http://databank.christuniversity.in/out1.php?' + params
resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
links4 = re.findall(r'<a href=[\'\"\s]?(odm_data/\d+\.dat)[\'\"\s]?>', resp, re.IGNORECASE)
print('Found', len(links4), 'links for 4 Semester')
