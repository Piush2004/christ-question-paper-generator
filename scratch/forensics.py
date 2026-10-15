import json, re
from pathlib import Path

with open('C:/Users/piush/.gemini/antigravity/brain/30f93120-7c0b-44c2-b5b9-a3c498485d3d/scratch/pdf_content.json', encoding='utf-8') as f:
    data = json.load(f)

for fname, content in data.items():
    if 'text' not in content: continue
    full_text = '\n'.join(content['text'])
    
    # Metadata extraction
    course_name_m = re.search(r'(?i)Course Name:\s*(.+)', full_text)
    course_code_m = re.search(r'(?i)Course Code:\s*([\w\-]+)', full_text)
    sem_m = re.search(r'(?i)SEMESTER - ([IVX]+)', full_text)
    if not sem_m: sem_m = re.search(r'(?i)UG ([IVX]+) Semester', full_text)
    
    year_m = re.search(r'(?i)END(?:-SEM)? EXAMINATIONS? - [a-zA-Z/]+ (\d{4})', full_text)
    exam_type_m = re.search(r'(?i)END(?:-SEM)? EXAMINATIONS?', full_text)
    
    # Marks patterns
    # Find all standalone numbers followed by (CO
    loose_marks = re.findall(r'(\d+(?:\.\d+)?)\s+\(CO\d', full_text)
    
    # Tables
    has_table = 'Q. No' in full_text and 'Questions' in full_text
    
    # Internal choices
    or_matches = re.findall(r'\bOR\b', full_text)
    either_matches = re.findall(r'\bEITHER\b', full_text)
    
    # Question numbering
    q_matches = re.findall(r'^\s*(?:Q\.\s*No\s*)?(\d{1,2}[\.\)])\s+', full_text, re.MULTILINE)
    
    print(f'=== {fname} ===')
    print(f'Subject: {course_name_m.group(1).strip() if course_name_m else "NOT DETERMINABLE"}')
    print(f'Course Code: {course_code_m.group(1).strip() if course_code_m else "NOT DETERMINABLE"}')
    print(f'Semester: {sem_m.group(1) if sem_m else "NOT DETERMINABLE"}')
    print(f'Year: {year_m.group(1) if year_m else "NOT DETERMINABLE"}')
    print(f'Exam Type: {exam_type_m.group(0).strip() if exam_type_m else "NOT DETERMINABLE"}')
    print(f'Table Format: {has_table}')
    print(f'Loose Marks (CO format): {len(loose_marks)}')
    print(f'Choices (OR/EITHER): {len(or_matches)} / {len(either_matches)}')
    print(f'Numbering examples: {q_matches[:5]}')
    
    # Sections
    sections = re.findall(r'(?i)SECTION\s+[A-Z]', full_text)
    print(f'Sections: {list(set(sections))}')
    
    print()
