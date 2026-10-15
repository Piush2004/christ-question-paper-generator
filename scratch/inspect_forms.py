import urllib.request
import re

url = 'http://databank.christuniversity.in/index.php?frmuser=christ&frmpass=library&login=Log+in'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
    print('HTML length:', len(html))
    
    # Find all select options
    select_matches = re.findall(r'<select[^>]*name=["\']?([^"\'>\s]+)[^>]*>(.*?)</select>', html, re.DOTALL | re.IGNORECASE)
    for name, content in select_matches:
        print(f"Select: {name}")
        options = re.findall(r'<option[^>]*value=["\']?([^"\'>\s]*)["\']?[^>]*>(.*?)</option>', content, re.IGNORECASE)
        for val, text in options:
            if 'Computer' in text or 'BCA' in text:
                print(f"  {val} -> {text.strip()}")
            if '1' in text and name == 'sem':
                print(f"  {val} -> {text.strip()}")
except Exception as e:
    print('Error:', e)
