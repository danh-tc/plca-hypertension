"""Build the English review PDF: renumber citations by first appearance, pandoc -> LaTeX -> xelatex."""
import re, subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).parent
TITLE = "Attribution is not mitigation: a paired-label counterfactual audit for hypertension clinical decision support"
AUTHOR = "Cong-Danh Tran"
AFFIL = "[Affiliation, City, Vietnam] · [email] · ORCID [ORCID]"

front = (ROOT / "front_src.md").read_text(encoding="utf-8")
body = (ROOT / "body_src.md").read_text(encoding="utf-8")
back = (ROOT / "back_src.md").read_text(encoding="utf-8")
appx = (ROOT / "appendix_src.md").read_text(encoding="utf-8")

# ---- reference list (shared with the Vietnamese version)
vi = (ROOT.parent / "vi" / "PLCA_ban_tieng_Viet_final.md").read_text(encoding="utf-8")
refs = {}
for l in vi.split("## Tài liệu tham khảo")[1].splitlines():
    m = re.match(r"(\d+)\.\s+(.*)", l)
    if m:
        refs[int(m.group(1))] = m.group(2).strip()

# references added after the Vietnamese version was frozen (English manuscript only)
refs[34] = refs[34].replace("Circulation 152 (2025)", "Circulation 152 (11) (2025)")
refs[41] = ("A. Lavin, C.M. Gilligan-Lee, A. Visnjic, S. Ganju, D. Newman, S. Ganguly, D. Lange, A.G. Baydin, "
            "A. Sharma, A. Gibson, S. Zheng, E.P. Xing, C. Mattmann, J. Parr, Y. Gal, Technology readiness levels for "
            "machine learning systems, Nat. Commun. 13 (2022) 6039, https://doi.org/10.1038/s41467-022-33128-9")
# ---- renumber citations by first appearance (body, then appendix)
CIT = re.compile(r"\[(\d+(?:\s*[–,-]\s*\d+)*)\]")
def expand(tok):
    out = []
    for part in tok.split(","):
        part = part.strip()
        if re.fullmatch(r"\d+\s*[–-]\s*\d+", part):
            a, b = map(int, re.split(r"\s*[–-]\s*", part)); out += list(range(a, b + 1))
        else:
            out.append(int(part))
    return out
order = []
for txt in (body, appx):
    for m in CIT.finditer(txt):
        for n in expand(m.group(1)):
            if n not in order:
                order.append(n)
new = {old: i + 1 for i, old in enumerate(order)}
def compress(nums):
    nums = sorted(set(nums)); out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1: j += 1
        out.append(str(nums[i]) if j == i else (f"{nums[i]},{nums[j]}" if j == i + 1 else f"{nums[i]}–{nums[j]}"))
        i = j + 1
    return ",".join(out)
sub = lambda txt: CIT.sub(lambda m: "[" + compress([new[n] for n in expand(m.group(1))]) + "]", txt)
body, appx = sub(body), sub(appx)
def brk(r):
    parts = re.split(r"(<https?://[^>]+>)", r)
    return "".join(p if p.startswith("<http") else re.sub(r"(?<=\w)/(?=\w)", r"/\\allowbreak{}", p) for p in parts)
reflist = "\n".join(f"{new[o]}. " + brk(re.sub(r"(https?://\S+?)(?=,?\s|,?$)", r"<\1>", refs[o])) for o in order)

def _path(m):
    s = m.group(1).replace("_", "\\_")
    return "\\texttt{" + s.replace("/", "/\\allowbreak{}").replace("\\_", "\\_\\allowbreak{}") + "}"
appx = re.sub(r"`(results/[^`]+|docs/[^`]+|scripts/[^`]+)`", _path, appx)
body = re.sub(r"`(scripts/[^`]+)`", _path, body)
def mathify(txt):
    pieces = re.split(r"(\$\$.*?\$\$|\$[^$\n]+\$|\\url\{[^}]*\}|`[^`]*`)", txt, flags=re.S)
    rules = [(r"p_m\(x′_abl\)", r"$p_m(x'_{\\mathrm{abl}})$"), (r"p_m\(x′\)", r"$p_m(x')$"), (r"p_m\(x\)", r"$p_m(x)$"),
             (r"Δ_m\(x′\)", r"$\\Delta_m(x')$"), (r"x′_abl", r"$x'_{\\mathrm{abl}}$"), (r"x′", r"$x'$"),
             (r"\bECD_(self|clin)\b", r"$\\mathrm{ECD}_{\\mathrm{\1}}$"), (r"\b([fgY])_(self|clin|placebo|bp)\b", r"$\1_{\\mathrm{\2}}$"), (r"\bg_m\b", r"$g_m$"),
             (r"\bR_sm\b", r"$R_{sm}$"), (r"\bA_(abl|after)\b", r"$A_{\\mathrm{\1}}$"), (r"\bC_(self|clin)\b", r"$C_{\\mathrm{\1}}$"), (r"\bC_m\b", r"$C_m$")]
    out = []
    for k, p in enumerate(pieces):
        if k % 2 == 0:
            for a, b2 in rules:
                p = re.sub(a, lambda m, b2=b2: m.expand(b2), p)
        elif p.startswith("$"):
            p = re.sub(r"_\{(self|clin|abl|after)\}", r"_{\\mathrm{\1}}", p)
            p = re.sub(r"\^\{\((self|clin)\)\}", r"^{(\\mathrm{\1})}", p)
        out.append(p)
    return "".join(out)
front, body, back, appx = mathify(front), mathify(body), mathify(back), mathify(appx)
md = (front + "\n\n" + body + "\n\n" + back + "\n\n# References\n\n::: {.refs}\n" + reflist + "\n:::\n\n"
      + "\\clearpage\n\n" + appx)
(ROOT / "paper_en.md").write_text(md, encoding="utf-8")
if "--md-only" in sys.argv:
    sys.exit(0)

header = r"""
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\setsansfont{TeX Gyre Heros}
\usepackage{newunicodechar}\newunicodechar{′}{\ensuremath{'}}
\usepackage[a4paper,margin=24mm]{geometry}
\usepackage{lineno}\linenumbers
\usepackage{float}\floatplacement{figure}{H}
\usepackage{caption}\captionsetup[figure]{labelformat=empty,font=small,justification=raggedright,singlelinecheck=false}
\usepackage{etoolbox}\AtBeginEnvironment{longtable}{\footnotesize}
\usepackage{setspace}\setstretch{1.25}
\usepackage{titlesec}
\titleformat{\section}{\large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\normalsize\bfseries\itshape}{}{0pt}{}
\usepackage{xcolor}\definecolor{elsblue}{HTML}{1F5FA6}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\footnotesize Tran · PLCA-Hypertension}\fancyhead[R]{\footnotesize Manuscript for review (not peer reviewed)}
\fancyfoot[C]{\footnotesize\thepage}\renewcommand{\headrulewidth}{0pt}
\renewcommand{\arraystretch}{1.15}
\setlength{\parskip}{3pt}\setlength{\emergencystretch}{3em}
\usepackage{xurl}
"""
(ROOT / "header.tex").write_text(header, encoding="utf-8")
before = (r"\begin{flushleft}{\LARGE\bfseries " + TITLE + r"\par}\vspace{8pt}{\large " + AUTHOR
          + r"\par}\vspace{2pt}{\small\itshape " + AFFIL.replace("·", r"\textperiodcentered{}") + r"\par}\end{flushleft}\vspace{4pt}")
(ROOT / "before.tex").write_text(before, encoding="utf-8")
subprocess.run(["pandoc", "paper_en.md", "-f", "markdown+pipe_tables+tex_math_dollars+fenced_divs-auto_identifiers",
                "-t", "latex", "-s", "-V", "fontsize=11pt", "-V", "documentclass=article",
                "-H", "header.tex", "-B", "before.tex", "-o", "paper_en.tex"], cwd=ROOT, check=True)
tex = (ROOT / "paper_en.tex").read_text(encoding="utf-8")
tex = tex.replace(r"\begin{refs}", "").replace(r"\end{refs}", "")
(ROOT / "paper_en.tex").write_text(tex, encoding="utf-8")
for _ in range(2):
    subprocess.run(["xelatex", "-interaction=nonstopmode", "paper_en.tex"], cwd=ROOT, stdout=subprocess.DEVNULL)
print("refs used:", len(order), "of", len(refs))
