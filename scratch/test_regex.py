import re
text1 = '5 (CO1, L1)'
text2 = '10 x 3 = 30 Marks'
text3 = '6'

pattern = re.compile(r'"^\s*(?:(?:Q(?:uestion)?\.?\s*)(\d{1,3})\b\.?|(\d{1,3})[.)](?:\s+|$)|(\d{1,3})\s*$)"', re.IGNORECASE)

print('text1:', bool(pattern.match(text1)))
print('text2:', bool(pattern.match(text2)))
print('text3:', bool(pattern.match(text3)))
