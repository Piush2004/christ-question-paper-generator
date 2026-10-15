import json, re
with open('C:/Users/piush/.gemini/antigravity/brain/30f93120-7c0b-44c2-b5b9-a3c498485d3d/scratch/pdf_content.json', encoding='utf-8') as f:
    data = json.load(f)

for fname, content in data.items():
    if 'text' not in content: continue
    full_text = '\n'.join(content['text'])
    
    course_name = re.search(r'(?i)Course Name:\s*(.+)', full_text)
    course_code = re.search(r'(?i)Course Code:\s*(.+)', full_text)
    sem = re.search(r'(?i)(?:SEMESTER -|UG)\s*([IVX]+)', full_text)
    year = re.search(r'(?i)(?:20\d\d)', full_text)
    
    sections = re.findall(r'SECTION\s+[A-Z]', full_text)
    or_count = len(re.findall(r'\bOR\b', full_text))
    
    print(f'[{fname}]')
    print(f'  Course: {course_name.group(1).strip() if course_name else "UNKNOWN"} ({course_code.group(1).strip() if course_code else "UNKNOWN"})')
    print(f'  Sem: {sem.group(1) if sem else "UNKNOWN"} | Year: {year.group(0) if year else "UNKNOWN"}')
    print(f'  Sections: {list(set(sections))}')
    print(f'  "OR" count: {or_count}')
