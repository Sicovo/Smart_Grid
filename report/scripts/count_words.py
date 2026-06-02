"""
Approximate word count for report.typ that strips Typst markup so the number
is closer to what a marker would count: comments, math, code, figure/table
function calls, citations, and section markers are removed.

Run:
    python scripts/count_words.py
"""

import os
import re

HERE = os.path.dirname(__file__)
REPORT = os.path.join(HERE, "..", "report.typ")

with open(REPORT, encoding="utf-8") as f:
    text = f.read()

raw = len(text.split())

# 1. Strip Typst line comments
text = re.sub(r"//[^\n]*", "", text)

# 2. Strip block math:  $ ... $  with spaces (display math)
text = re.sub(r"\$ [^$]*? \$", " ", text, flags=re.DOTALL)

# 3. Strip inline math:  $...$
text = re.sub(r"\$[^$\n]+?\$", " ", text)

# 4. Strip backtick inline code
text = re.sub(r"`[^`]*`", " ", text)

# 5. Strip multi-line Typst directives starting with #
#    (e.g. #figure(...), #protable(...), #set ...)
lines = text.split("\n")
kept = []
paren_depth = 0
for line in lines:
    s = line.strip()
    if paren_depth > 0:
        paren_depth += s.count("(") - s.count(")")
        if paren_depth < 0:
            paren_depth = 0
        continue
    if s.startswith("#"):
        opens = s.count("(")
        closes = s.count(")")
        if opens > closes:
            paren_depth = opens - closes
        # Skip the whole directive whether single-line or multi-line.
        continue
    kept.append(line)
text = "\n".join(kept)

# 6. Strip section heading markers ('= Title' -> 'Title') so headings still count.
text = re.sub(r"^={1,6}\s+", "", text, flags=re.MULTILINE)

# 7. Strip @citation keys
text = re.sub(r"@[A-Za-z0-9_:]+", "", text)

# 8. Strip Typst figure label anchors  <fig:something>
text = re.sub(r"<[A-Za-z0-9_:\-]+>", " ", text)

body = len(text.split())

print(f"Raw word count (everything):     {raw:>6}")
print(f"Body prose estimate (no markup): {body:>6}")
print(f"Budget remaining (vs 10,000):    {10000 - body:>6}")
