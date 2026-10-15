import re
text = '''State Euler's formula for planar graphs and verify the same for the
following graphs. (i) G4  (ii) K4.
CO3
L5'''

co_match = re.search(r'"\b(CO[1-6])\b"', text, re.IGNORECASE)
rbt_match = re.search(r'"\b(L[1-6])\b"', text, re.IGNORECASE)
print('CO:', co_match.group(1) if co_match else None)
print('RBT:', rbt_match.group(1) if rbt_match else None)
