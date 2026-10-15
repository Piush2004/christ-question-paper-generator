import fitz
from pathlib import Path

raw_dir = Path('data/raw')
pdfs = list(raw_dir.glob('*.pdf'))

for pdf_path in pdfs:
    print(f'
--- {pdf_path.name} ---')
    try:
        doc = fitz.open(pdf_path)
        print(f'Pages: {len(doc)}')
        for i in range(min(2, len(doc))):
            page = doc[i]
            text = page.get_text()
            print(f'
[Page {i+1}]')
            print(text[:1000] + '...' if len(text) > 1000 else text)
            print('-' * 40)
    except Exception as e:
        print(f'Error reading {pdf_path}: {e}')
