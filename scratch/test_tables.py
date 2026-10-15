import pymupdf as fitz
from pathlib import Path
doc = fitz.open('data/raw/BCA431 2024.pdf')
page = doc[0]
tabs = page.find_tables()
print(f'Found {len(tabs.tables)} tables')
for tab in tabs.tables:
    df = tab.to_pandas()
    print(df.head())
