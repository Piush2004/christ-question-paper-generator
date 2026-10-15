import re
text = 'Section A'
SECTION_HEADER = re.compile(
    r'"^\s*(section|part)\s*[-:]?\s*([A-Z]|[IVXivx]+|\d+)\b"',
    re.IGNORECASE,
)
print(SECTION_HEADER.match(text))
