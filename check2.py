import re, time
t = open('p2.html').read()

# Get ALL frag IDs - the pagination ones
frags = re.findall(r"selectPage[',\s]+(\d+)[,\s]+\{[^}]*FRAGID[_'\":\s]+(\d+)", t)
print('selectPage + fragID pairs:', frags[:5])

# Try another approach - find frag ID near selectPage
ctx = re.findall(r".{50}selectPage.{200}", t)
for c in ctx[:2]:
    print(c)
    print('---')
