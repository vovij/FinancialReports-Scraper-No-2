"""
Run this locally: python diagnose.py
It reads page_dump.html and prints everything needed to fix pagination.
"""
import re
from bs4 import BeautifulSoup

html = open("page_dump.html").read()
soup = BeautifulSoup(html, "html.parser")

print("=" * 60)
print("1. ALL selectPage JS calls")
print("=" * 60)
for m in re.finditer(r'.{0,20}selectPage.{0,200}', html):
    print(m.group())
print()

print("=" * 60)
print("2. ALL hidden inputs (Catalyst state fields)")
print("=" * 60)
for inp in soup.find_all("input", type="hidden"):
    print(f"  name={inp.get('name','?')!r:40s} value={str(inp.get('value',''))[:60]!r}")
print()

print("=" * 60)
print("3. Pagination element HTML")
print("=" * 60)
for el in soup.select("[class*='appPag'], [class*='Paginat'], [class*='paginat']"):
    print(el.prettify()[:800])
    print("---")
print()

print("=" * 60)
print("4. All W### widget IDs on page")
print("=" * 60)
ids = re.findall(r'\b(W\d{2,4})\b', html)
print(list(dict.fromkeys(ids))[:30])
print()

print("=" * 60)
print("5. XHR / fetch / async calls")
print("=" * 60)
for m in re.finditer(r'.{0,10}(catAsync|catHtml|catPost|_CBNODE_|XMLHttp|fetch\().{0,150}', html):
    print(m.group()[:200])
print()

print("=" * 60)
print("6. Form action URLs")
print("=" * 60)
for form in soup.find_all("form"):
    print(f"  action={form.get('action','?')}  method={form.get('method','?')}")