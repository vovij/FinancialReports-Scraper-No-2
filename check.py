import re
t = open('p2.html').read()

frags = re.findall(r'CBHTMLFRAGID[^0-9]+(\d{10,})', t)
print('frag IDs:', frags[:5])

print('is full page:', '<html' in t[:500])
print('size:', len(t))

# Find any selectPage call
pages = re.findall(r"selectPage','(\d+)", t)
print('selectPage numbers:', pages[:10])
