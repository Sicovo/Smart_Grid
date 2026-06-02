"""
Per-section approximate word count for report.typ.

Strips Typst markup similar to count_words.py, but also captures captions
inside #figure(caption: [...]) and #protable(caption: [...]) since markers
do count caption text. Breaks the count down by `= Section` heading so we
can see where the bulk lives.

Run:
    python scripts/count_words_per_section.py
"""

import os
import re

HERE = os.path.dirname(__file__)
REPORT = os.path.join(HERE, "..", "report.typ")

with open(REPORT, encoding="utf-8") as f:
    text = f.read()

# Strip Typst line comments
text = re.sub(r"//[^\n]*", "", text)

# Strip block math:  $ ... $
text = re.sub(r"\$ [^$]*? \$", " ", text, flags=re.DOTALL)
text = re.sub(r"\$[^$\n]+?\$", " ", text)

# Strip backtick inline code
text = re.sub(r"`[^`]*`", " ", text)

# Strip @citations
text = re.sub(r"@[A-Za-z0-9_:]+", "", text)

# Strip figure labels  <fig:...>
text = re.sub(r"<[A-Za-z0-9_:\-]+>", " ", text)


def strip_typst_calls(s):
    """
    Strip lines that are pure Typst directives, but PRESERVE caption text
    and table cell strings that sit inside #figure(...) / #protable(...).
    Approach: keep any [ ... ] bracket content (Typst content blocks),
    drop the rest of the directive (keywords, function names, arg names,
    columns/align/width/etc).
    """
    out_lines = []
    paren_depth = 0
    inside_directive = False
    for line in s.split("\n"):
        stripped = line.strip()
        if not inside_directive and stripped.startswith("#"):
            opens = stripped.count("(")
            closes = stripped.count(")")
            balance = opens - closes
            if balance > 0:
                inside_directive = True
                paren_depth = balance
                # Extract any [ ... ] content from this opening line
                bracket_text = " ".join(re.findall(r"\[([^\[\]]*)\]", stripped))
                if bracket_text:
                    out_lines.append(bracket_text)
            # else: single-line #directive, skip entirely
            continue
        if inside_directive:
            paren_depth += line.count("(") - line.count(")")
            # Pull out [ ... ] cells/captions/content
            brackets = re.findall(r"\[([^\[\]]*)\]", line)
            if brackets:
                out_lines.append(" ".join(brackets))
            if paren_depth <= 0:
                inside_directive = False
                paren_depth = 0
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


text = strip_typst_calls(text)

# Strip section heading markers but keep heading words
text = re.sub(r"^={1,6}\s+", "", text, flags=re.MULTILINE)

# Split into sections by re-injecting markers
with open(REPORT, encoding="utf-8") as f:
    raw = f.read()

# Find positions of `= TopHeading` to split
section_pattern = re.compile(r"^= ([^\n]+)$", re.MULTILINE)
sections = []
for m in section_pattern.finditer(raw):
    sections.append((m.start(), m.group(1).strip()))

# Process each section's slice through the same strippers
def strip_pipeline(s):
    s = re.sub(r"//[^\n]*", "", s)
    s = re.sub(r"\$ [^$]*? \$", " ", s, flags=re.DOTALL)
    s = re.sub(r"\$[^$\n]+?\$", " ", s)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"@[A-Za-z0-9_:]+", "", s)
    s = re.sub(r"<[A-Za-z0-9_:\-]+>", " ", s)
    s = strip_typst_calls(s)
    s = re.sub(r"^={1,6}\s+", "", s, flags=re.MULTILINE)
    return s


print(f"{'#':>2}  {'Section':<48} {'Words':>7}")
print("-" * 60)
total = 0
for i, (start, name) in enumerate(sections):
    end = sections[i + 1][0] if i + 1 < len(sections) else len(raw)
    slice_text = raw[start:end]
    words = len(strip_pipeline(slice_text).split())
    total += words
    print(f"{i+1:>2}  {name[:48]:<48} {words:>7}")
print("-" * 60)
print(f"    {'TOTAL':<48} {total:>7}")
