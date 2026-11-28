"""Main-text word count (IJMI: excludes abstract, tables, figure captions, references, appendices).
Counts body_src.md prose only: drops tables, figure lines, table captions/notes and display math."""
import re, sys
t = open(sys.argv[1] if len(sys.argv) > 1 else "body_src.md", encoding="utf-8").read()
t = re.sub(r"\$\$.*?\$\$", " ", t, flags=re.S)
keep = []
for line in t.splitlines():
    s = line.strip()
    if s.startswith("|") or s.startswith("![") or s.startswith("**Table") or (s.startswith("*") and s.endswith("*") and not s.startswith("**")):
        continue
    keep.append(re.sub(r"^#+\s*", "", s))
words = re.findall(r"[A-Za-z0-9][\w'’./–−-]*", " ".join(keep))
print(len(words))
