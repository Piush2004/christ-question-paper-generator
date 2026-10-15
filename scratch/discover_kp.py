import urllib.request
import urllib.parse
import http.cookiejar
import re
import csv
import time
from pathlib import Path

def discover_corpus():
    base_dir = Path("d:/Projects/Christ Question Paper model/data/raw/knowledgepro")
    discovery_dir = base_dir / "discovery"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = discovery_dir / "bca_catalog.csv"
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # Login
    for attempt in range(3):
        try:
            opener.open('http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in', timeout=15)
            break
        except Exception as e:
            print(f"Login retry {attempt}: {e}")
            time.sleep(2)
            
    catalog_rows = []
    
    for sem in range(1, 7):
        url = 'http://databank.christuniversity.in/out1.php?' + urllib.parse.urlencode({
            'where': '1', 
            'keyword': 'Bachelor', 
            'sem': str(sem), 
            'submit': 'Search'
        })
        
        success = False
        for attempt in range(3):
            try:
                print(f"Fetching sem {sem} (attempt {attempt+1})...")
                res = opener.open(url, timeout=20)
                html = res.read().decode('utf-8')
                success = True
                break
            except Exception as e:
                print(f"Error on sem {sem}: {e}")
                time.sleep(3)
                
        if not success:
            print(f"Failed to fetch semester {sem} after retries.")
            continue
            
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
        found = 0
        for i, row in enumerate(rows):
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
            cols = [re.sub(r'<[^>]+>', '', c).replace('&nbsp;', ' ').strip() for c in cols]
            
            links = re.findall(r'href=["\']?([^"\'>]+\.dat)["\']?', row, re.IGNORECASE)
            if not links:
                continue
            
            link = links[0]
            row_text = ' '.join(cols)
            
            if 'BCA' in row_text or 'Computer Applications' in row_text:
                course_code = cols[0] if len(cols) > 0 else 'UNKNOWN'
                course_name = cols[1] if len(cols) > 1 else 'UNKNOWN'
                exam_name = cols[2] if len(cols) > 2 else 'UNKNOWN'
                
                catalog_rows.append({
                    'programme': 'BCA',
                    'semester': str(sem),
                    'course_code': course_code,
                    'course_name': course_name,
                    'exam_name': exam_name,
                    'download_url': 'http://databank.christuniversity.in/' + link
                })
                found += 1
        print(f"Discovered {found} papers for semester {sem}.")
        time.sleep(2)
            
    with open(catalog_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['programme', 'semester', 'course_code', 'course_name', 'exam_name', 'download_url'])
        writer.writeheader()
        writer.writerows(catalog_rows)
        
    print(f"\nDiscovered {len(catalog_rows)} total BCA papers across 6 semesters.")

if __name__ == '__main__':
    discover_corpus()
