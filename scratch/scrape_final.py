import urllib.request, urllib.parse, urllib.error
from http.cookiejar import CookieJar
import re
import os

cj = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
opener.open(url).read()

# Make directory if not exists
os.makedirs('data/raw/databank', exist_ok=True)

# We want to iterate through semesters using the first form actually.
# Wait, let's test Form 0 first. We need the actual values for Undergraduate and BCA.
# Looking at the HTML:
# <option value='1'>Undergraduate</option>
# But Course dropdown is loaded dynamically! "<select id='ddlView2' name='keyword'><option value=''>Select one</option></select>"
# Since it's dynamic, I can't easily use Form 0 without knowing the Course ID.

# Let's use Form 1 and loop through typical BCA course codes:
# BCA101, BCA102, BCA103, BCA104, BCA201, BCA202, BCA301, BCA302, BCA431, BCA432, BCA433, BCA434
codes = ['BCA101', 'BCA102', 'BCA103', 'BCA104', 'BCA131', 'BCA201', 'BCA202', 'BCA301', 'BCA302', 'BCA431', 'BCA434']

total_downloaded = 0
for code in codes:
    params = urllib.parse.urlencode({'keyword': code, 'where': 'all', 'submit': 'Search'})
    res_url = 'http://databank.christuniversity.in/out.php?' + params
    print(f'Fetching {code}...')
    resp = opener.open(res_url).read().decode('utf-8', errors='ignore')
    links = re.findall(r'<a href=[\'\"\s]?(odm_data/\d+\.dat)[\'\"\s]?>', resp, re.IGNORECASE)
    print(f'Found {len(links)} links for {code}')
    
    # Download them
    for link in links:
        dl_url = 'http://databank.christuniversity.in/' + link
        filename = link.split('/')[-1].replace('.dat', f'_{code}.pdf') # Make it a pdf
        filepath = os.path.join('data/raw/databank', filename)
        if not os.path.exists(filepath):
            try:
                pdf_data = opener.open(dl_url).read()
                with open(filepath, 'wb') as f:
                    f.write(pdf_data)
                total_downloaded += 1
                print(f'  Downloaded {filename}')
            except Exception as e:
                print(f'  Failed to download {dl_url}: {e}')

print(f'Finished! Total downloaded: {total_downloaded}')
