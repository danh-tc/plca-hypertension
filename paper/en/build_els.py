"""Build the English manuscript with Elsevier's elsarticle class.

python build_els.py submission  -> paper_en_submission.pdf (single column, double spacing, line numbers)
python build_els.py journal     -> paper_en_journal.pdf    (5p two-column journal look, for reading)
"""
import re, sys, subprocess, pathlib

MODE = sys.argv[1] if len(sys.argv) > 1 else "submission"
ROOT = pathlib.Path(__file__).parent
TITLE = "Attribution is not mitigation: a paired-label counterfactual audit of hypertension classification models"

# reuse citation renumbering and symbol typesetting from build_en.py (writes paper_en.md)
subprocess.run([sys.executable, "build_en.py", "--md-only"], cwd=ROOT, check=True)
md = (ROOT / "paper_en.md").read_text(encoding="utf-8")

def esc(s):
    out, parts = [], re.split(r"(\$[^$]+\$|\\url\{[^}]*\})", s)
    for k, p in enumerate(parts):
        if k % 2:
            out.append(p); continue
        p = (p.replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
               .replace("_", r"\_").replace("~", r"\textasciitilde{}").replace("^", r"\^{}"))
        p = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", p)
        p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\textit{\1}", p)
        p = re.sub(r"`([^`]+)`", r"\\texttt{\1}", p)
        p = p.replace(r"\textbackslash{}|", "|").replace("\\textbackslash{}", "\\textbackslash{}")
        out.append(p)
    return "".join(out).replace(r"\textbackslash{}|", "|")

def cells(line):
    line = line.strip().strip("|")
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]

WIDE = {"2", "3", "A4", "A6", "1", "A1", "A5", "A3", "A2", "A7", "A8"}
def table(num, cap, rows, note):
    n = len(rows[0])
    two = MODE == "journal"
    env = "table*" if (two and num in WIDE) else "table"
    width = r"\textwidth" if env == "table*" or not two else r"\columnwidth"
    first = {"A7": "0.16", "A8": "0.20", "2": "0.24", "A6": "0.30", "3": "0.10", "A5": "0.30", "A4": "0.22", "1": "0.18", "5": "0.40"}.get(num)
    spec = (r">{\raggedright\arraybackslash}p{%s\linewidth}" % first if first else r">{\raggedright\arraybackslash}X") \
        + r">{\raggedright\arraybackslash}X" * (n - 1)
    if num == "A8":
        L = r">{\raggedright\arraybackslash}"
        spec = L + r"p{0.19\linewidth}" + L + r"p{0.21\linewidth}" + L + r"X" + L + r"p{0.07\linewidth}" + L + r"X" + L + r"p{0.07\linewidth}"
    body = []
    for k, r in enumerate(rows):
        c = [esc(x) for x in r]
        body.append(" & ".join(r"\textbf{%s}" % x for x in c) + r" \\ \midrule" if k == 0 else " & ".join(c) + r" \\")
    s = [r"\begin{%s}[!htbp]" % env, r"\caption{%s}" % esc(cap), r"\label{tab%s}" % num, (r"\scriptsize" if num in ("A7", "A8") else r"\footnotesize") + r"\def\baselinestretch{1}\selectfont\renewcommand{\arraystretch}{1.1}",
         r"\begin{tabularx}{%s}{%s}" % (width, spec), r"\toprule"] + body + [r"\bottomrule", r"\end{tabularx}"]
    if note:
        s.append(r"\par\vspace{2pt}{\scriptsize\raggedright " + esc(note.strip().strip("*")) + r"\par}")
    s.append(r"\end{%s}" % env)
    return "\n```{=latex}\n" + "\n".join(s) + "\n```\n"

def figure(cap, f):
    wide = f == "fig1.pdf" and MODE == "journal"
    env = "figure*" if wide else "figure"
    w = r"\textwidth" if wide else (r"\columnwidth" if MODE == "journal" else r"0.85\textwidth")
    m = re.match(r"(Fig\. A?\d+)\.\s*(.*)", cap)
    return ("\n```{=latex}\n" + r"\begin{%s}[!htbp]\centering\includegraphics[width=%s]{%s}" % (env, w, f)
            + r"\caption{%s}\end{%s}" % (esc(m.group(2)), env) + "\n```\n")

# ---- split front / body / refs / appendix
front, rest = md.split("# 1. Introduction", 1)
rest = "# 1. Introduction" + rest
body, refs_and_appx = rest.split("# References", 1)
mm = re.search(r"::: \{\.refs\}\n(.*?)\n:::\n(.*)", refs_and_appx, re.S)
refs_block, appx = mm.group(1), mm.group(2)
refs = re.findall(r"^\d+\.\s+(.*)$", refs_block, re.M)

hl = re.findall(r"^- (.*)$", front.split("## Abstract")[0], re.M)
abstract = re.findall(r"^\*\*(Background|Objective|Methods|Results|Conclusion)\.\*\*\s*(.*)$", front, re.M)
keywords = re.search(r"\*\*Keywords:\*\*\s*(.*)", front).group(1).split(";")
summary = front.split("## Summary table", 1)[1]

def convert(text):
    lines, out, k = text.split("\n"), [], 0
    while k < len(lines):
        l = lines[k]
        m = re.match(r"\*\*Table (\w+)\.\*\*\s*(.*)", l)
        if m:
            j = k + 1
            while j < len(lines) and not lines[j].startswith("|"): j += 1
            rows = []
            while j < len(lines) and lines[j].startswith("|"):
                c = cells(lines[j])
                if not all(re.fullmatch(r":?-{3,}:?", x) for x in c): rows.append(c)
                j += 1
            jj = j
            while jj < len(lines) and not lines[jj].strip(): jj += 1
            note = ""
            if jj < len(lines) and lines[jj].startswith("*") and not lines[jj].startswith("**"):
                note = lines[jj]; j = jj + 1
            out.append(table(m.group(1), m.group(2), rows, note)); k = j; continue
        m = re.match(r"!\[(.*)\]\((\S+)\)(\{.*\})?", l)
        if m:
            out.append(figure(m.group(1), m.group(2))); k += 1; continue
        out.append(l); k += 1
    return "\n".join(out)

def pandoc(text, shift=0):
    (ROOT / "_tmp.md").write_text(text, encoding="utf-8")
    args = ["pandoc", "_tmp.md", "-f", "markdown+raw_attribute+tex_math_dollars-auto_identifiers", "-t", "latex", "-o", "_tmp.tex"]
    if shift: args.insert(-2, f"--shift-heading-level-by={shift}")
    subprocess.run(args, cwd=ROOT, check=True)
    t = (ROOT / "_tmp.tex").read_text(encoding="utf-8")
    t = re.sub(r"\\(section|subsection|subsubsection)\{(\d+(?:\.\d+)*)\.?\s+", r"\\\1{", t)   # elsarticle numbers sections
    return t

body_tex = pandoc(convert(body))
body_tex = re.sub(r"\\section\{(CRediT|Declaration|Funding|Ethics|Data availability|Patient and public involvement)", r"\\section*{\1", body_tex)
summary_tex = pandoc(summary)
appx_tex = pandoc(convert(appx.replace("\\clearpage", "")))
appx_tex = appx_tex.replace(r"\section{Appendix A. Supplementary material}", r"\section{Supplementary material}")

def reftex(r):
    r = r.replace("\\allowbreak{}", "")
    t = esc(re.sub(r"<(https?://[^>]+)>", r"\\url{\1}", r))
    parts = re.split(r"(\\url\{[^}]*\})", t)
    return "".join(p if p.startswith("\\url") else re.sub(r"(?<=\w)/(?=\w)", r"/\\allowbreak{}", p) for p in parts)
refs_tex = "\n".join(r"\bibitem{r%d} %s" % (i + 1, reftex(r)) for i, r in enumerate(refs))
refs_tex = refs_tex.replace(r"\textbackslash{}allowbreak\{\}", "").replace(r"\allowbreak\{\}", r"\allowbreak{}")

if MODE == "journal":
    cls = r"\documentclass[final,5p,times,twocolumn]{elsarticle}"
    extra = ""
else:
    cls = r"\documentclass[preprint,review,12pt,times]{elsarticle}"
    extra = r"\usepackage{lineno}\linenumbers"

doc = cls + r"""
\usepackage{iftex}\ifPDFTeX\usepackage[T1]{fontenc}\usepackage[utf8]{inputenc}\usepackage{textcomp}\renewcommand{\ttdefault}{lmtt}\else\usepackage{fontspec}\setmainfont{TeX Gyre Termes}\fi
\usepackage{newunicodechar}\newunicodechar{′}{\ensuremath{'}}\newunicodechar{−}{\ensuremath{-}}\newunicodechar{≥}{\ensuremath{\geq}}\newunicodechar{≤}{\ensuremath{\leq}}\newunicodechar{×}{\ensuremath{\times}}\newunicodechar{Δ}{\ensuremath{\Delta}}\newunicodechar{→}{\ensuremath{\rightarrow}}\newunicodechar{Σ}{\ensuremath{\Sigma}}
\usepackage{amsmath,amssymb,graphicx,booktabs,tabularx,array,xurl,needspace}
\makeatletter\def\ps@pprintTitle{\let\@oddhead\@empty\let\@evenhead\@empty\let\@oddfoot\@empty\let\@evenfoot\@oddfoot}\makeatother
\usepackage[hidelinks]{hyperref}\usepackage{orcidlink}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setlength{\emergencystretch}{3em}
""" + extra + r"""
\journal{International Journal of Medical Informatics}
\begin{document}
\begin{frontmatter}
\title{""" + esc(TITLE) + r"""}
\author[uit,vnu]{Cong-Danh Tran}
\makeatletter\g@addto@macro\elsauthors{\,\orcidlink{0009-0001-9660-8808}}\makeatother
\ead{danhtc@grad.uit.edu.vn}
\affiliation[uit]{organization={University of Information Technology}, city={Ho Chi Minh City}, country={Viet Nam}}
\affiliation[vnu]{organization={Vietnam National University}, city={Ho Chi Minh City}, country={Viet Nam}}
\begin{abstract}
""" + "\n\n".join(r"\textbf{%s:} %s" % (a, esc(b)) for a, b in abstract) + r"""
\end{abstract}
""" + (r"\begin{highlights}" + "\n" + "\n".join(r"\item " + esc(h) for h in hl) + "\n" + r"\end{highlights}" if MODE == "submission" else "") + r"""
\begin{keyword}
""" + r" \sep ".join(esc(k.strip()) for k in keywords) + r"""
\end{keyword}
\end{frontmatter}
""" + body_tex.split(r"\section*{CRediT")[0] + r"""
\needspace{16\baselineskip}\section*{Summary table}
""" + summary_tex + "\n" + r"\section*{CRediT" + body_tex.split(r"\section*{CRediT", 1)[1] + r"""
\begin{thebibliography}{99}
""" + refs_tex + r"""
\end{thebibliography}
\clearpage
\appendix
\setcounter{table}{0}\setcounter{figure}{0}
""" + appx_tex + r"""
\end{document}
"""
name = f"paper_en_{MODE}"
(ROOT / f"{name}.tex").write_text(doc, encoding="utf-8")
for _ in range(2):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", f"{name}.tex"], cwd=ROOT, stdout=subprocess.DEVNULL)
print("built", name, "refs", len(refs))
