"""Build an Elsevier-style two-column Vietnamese PDF from the exported Claude Doc markdown."""
import re, subprocess, pathlib

ROOT = pathlib.Path(__file__).parent
md = (ROOT / "paper_master.md").read_text(encoding="utf-8").splitlines()

# ---------------------------------------------------------------- helpers
def unesc(s):
    s = s.replace("&#91;", "[")
    return re.sub(r"\\([\[\]_*|#\\`<>()!-])", r"\1", s)

def tex(s):
    """markdown inline -> LaTeX (tables, captions, front matter)."""
    s = unesc(s)
    out, i = [], 0
    for part in re.split(r"(`[^`]+`)", s):
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(r"\texttt{" + esc(part[1:-1]) + "}")
        else:
            p = esc(part)
            p = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", p)
            p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\textit{\1}", p)
            out.append(p)
    return "".join(out)

def esc(p):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}"}
    return "".join(rep.get(c, c) for c in p)

def split_row(line):
    line = line.strip().strip("|")
    cells, cur, i = [], "", 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            cur += line[i:i + 2]; i += 2; continue
        if line[i] == "|":
            cells.append(cur.strip()); cur = ""
        else:
            cur += line[i]
        i += 1
    cells.append(cur.strip())
    return cells

def table_tex(num, caption, rows, note):
    ncol = len(rows[0])
    wide = (ncol >= 5 or num == "2") and not num.startswith("A")
    env = "table*" if wide else "table"
    width = r"\textwidth" if wide else r"\columnwidth"
    if num == "1":
        spec = r">{\raggedright\arraybackslash}p{0.27\textwidth}" + r">{\raggedleft\arraybackslash}X" * (ncol - 1)
    elif num == "3":
        spec = (r">{\raggedright\arraybackslash}p{0.11\textwidth}>{\raggedright\arraybackslash}p{0.19\textwidth}"
                + r">{\raggedright\arraybackslash}X" * 3 + r">{\raggedright\arraybackslash}p{0.10\textwidth}")
    else:
        spec = r">{\raggedright\arraybackslash}X" * ncol
    body = []
    for k, r in enumerate(rows):
        cells = [tex(c) for c in r]
        if k == 0:
            cells = [r"\textbf{" + c + "}" for c in cells]
            body.append(" & ".join(cells) + r" \\ \midrule")
        elif all(not c for c in r[1:]) and r[0].startswith("**"):
            body.append(r"\multicolumn{%d}{l}{%s} \\" % (ncol, cells[0]))
        else:
            body.append(" & ".join(cells) + r" \\")
    s = [r"\begin{%s}[%s]" % (env, "h!" if num.startswith("A") else "!t"), r"\tabcap{%s}{%s}" % (num, tex(caption)),
         r"\begin{tabularx}{%s}{%s}" % (width, spec), r"\toprule"] + body + [r"\bottomrule", r"\end{tabularx}"]
    if note:
        s.append(r"\tabnote{" + tex(note.strip("*")) + "}")
    s.append(r"\end{%s}" % env)
    return "\n```{=latex}\n" + "\n".join(s) + "\n```\n"

FIGS = {
    "1": ("fig1.png", r"0.66\textwidth", "figure*",
          "Thiết kế quy trình kiểm định nhãn kép (PLCA). Hai mô hình chỉ khác nhau ở nhãn. Ở tầng CF, mỗi CF được đưa vào cả hai mô hình phụ để tính điểm, tạo thành ma trận 2 × 2 cùng nhãn – khác nhãn (ô tô đậm là cùng nhãn). E6 phân tích đóng góp trên các CF đã sinh; E3 đánh giá việc sinh CF mới khi cấm thay đổi nhóm biến."),
    "2": ("fig2.png", r"\columnwidth", "figure",
          "Mức giảm AUC khi hoán vị từng nhóm biến ở ba mô hình (NHANES 2015–2018, seed 42, bootstrap hai tầng B = 100). "
          "Chấm là ước lượng điểm, vạch là khoảng 95\\%. Không vẽ nhóm nhân khẩu học (f\\_self 0,103; f\\_clin 0,211)."),
    "3": ("fig3.png", r"\columnwidth", "figure",
          "Độ bất đối xứng chuyển giao A trên cùng tập bệnh nhân S* ở mỗi seed: CF với ràng buộc cơ sở (M0), CF đã sinh sau khi hoàn nguyên, "
          "và CF sinh mới khi cấm thay đổi nhóm biến (M2). Mức giảm dưới mỗi nhóm tính theo độ lớn |A|; ở seed 43, A đổi dấu sau khi hoàn nguyên."),
    "4": ("fig4.png", r"\columnwidth", "figure",
          "Tỷ lệ người có ít nhất một CF hợp lệ ở M0 (ràng buộc cơ sở), M2 (cấm nhóm biến liên quan đến chẩn đoán) "
          "và M1 (T-HTN), theo mô hình sinh CF và seed (200 người được chọn ở mỗi seed)."),
}

def fig_tex(n):
    f, w, env, cap = FIGS[n]
    return ("\n```{=latex}\n" + r"\begin{%s}[!t]\centering\includegraphics[width=%s]{%s}" % (env, w, f)
            + r"\figcap{%s}{%s}\end{%s}" % (n, cap, env) + "\n```\n")

def math_tex(lines):
    body = "\n".join(lines)
    parts = [p.strip() for p in body.split(r"\qquad")]
    if len(parts) > 1:
        return "\n```{=latex}\n\\begin{gather*}\n" + " \\\\[3pt]\n".join(parts) + "\n\\end{gather*}\n```\n"
    return "\n```{=latex}\n\\[\n" + body + "\n\\]\n```\n"

# ---------------------------------------------------------------- front matter
def grab(prefix):
    return next(l for l in md if l.startswith(prefix))

title = re.sub(r"^## ", "", md[4]).strip()
gloss = md[6].strip().strip("*").strip("()")
hl = []
i = md.index("### Highlights") + 1
while not md[i].startswith("- "): i += 1
while md[i].startswith("- "): hl.append(md[i][2:]); i += 1
keywords = [k.strip() for k in grab("**Keywords:**").split("**")[2].split(";")]
abs_labels = {"Background": "Bối cảnh", "Objectives": "Mục tiêu", "Methods": "Phương pháp",
              "Results": "Kết quả", "Conclusions": "Kết luận"}
abstract = []
for l in md:
    m = re.match(r"\*\*(Background|Objectives|Methods|Results|Conclusions)\.\*\*\s*(.*)", l)
    if m:
        abstract.append(r"\textbf{%s.} %s" % (abs_labels[m.group(1)], tex(m.group(2))))

# ---------------------------------------------------------------- body
start = md.index("## 1. Mở đầu")
end = next(k for k, l in enumerate(md) if l.startswith("### Hình và bảng dự kiến"))
lines = md[start:end]
out, k = [], 0
refs = []
while k < len(lines):
    l = lines[k]
    if l.startswith("### References"):
        k += 1
        while k < len(lines):
            m = re.match(r"\d+\.\s+(.*)", lines[k])
            if m:
                refs.append(m.group(1))
            k += 1
        break
    m = re.match(r"\*\*Bảng (\w+)\.\*\*\s*(.*)", l)
    if m:
        j = k + 1
        while j < len(lines) and not lines[j].startswith("|"): j += 1
        rows = []
        while j < len(lines) and lines[j].startswith("|"):
            r = split_row(lines[j])
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in r):
                rows.append(r)
            j += 1
        note = ""
        jj = j
        while jj < len(lines) and not lines[jj].strip(): jj += 1
        if jj < len(lines) and lines[jj].startswith("*") and not lines[jj].startswith("**"):
            note = lines[jj]; j = jj + 1
        out.append(table_tex(m.group(1), m.group(2), rows, note))
        k = j; continue
    m = re.match(r"\[embedded content: Hình (\d)", unesc(l))
    if m:
        out.append(fig_tex(m.group(1))); k += 1; continue
    if l.startswith("```latex"):
        j = k + 1; buf = []
        while not lines[j].startswith("```"):
            buf.append(lines[j]); j += 1
        out.append(math_tex(buf)); k = j + 1; continue
    m = re.match(r"### (\d+\.\d+) (.*)", l)
    if m:
        l = "### %s. %s" % (m.group(1), m.group(2))
    out.append(l); k += 1

body_md = "\n".join(out)
(ROOT / "body.md").write_text(body_md, encoding="utf-8")
subprocess.run(["pandoc", "body.md", "-f", "markdown+raw_attribute+pipe_tables-auto_identifiers",
                "-t", "latex", "--shift-heading-level-by=-1", "-o", "body.tex"], cwd=ROOT, check=True)
body = (ROOT / "body.tex").read_text(encoding="utf-8")

def ref_tex(r):
    r = re.sub(r"\s*\(T\)\s*$", "", r)
    t = tex(r)
    t = re.sub(r"(https://\S+?)(?=[,\s]|$)", lambda m: r"\url{" + m.group(1).replace(r"\_", "_") + "}", t)
    return t
refs_tex = "\n".join(r"\bibitem{} " + ref_tex(r) for r in refs)

front = r"""
\twocolumn[{%
\begin{center}
{\small\color{elsblue} PLCA-Hypertension \textperiodcentered{} Bản thảo tiếng Việt để review \textperiodcentered{} chưa qua bình duyệt}\\[2pt]
{\color{rulegray}\rule{\textwidth}{0.4pt}}\\[-1pt]
\colorbox{bandgray}{\parbox{\dimexpr\textwidth-2\fboxsep}{\centering\vspace{5pt}
{\fontsize{17}{20}\selectfont\color{black!85} Bản thảo dự kiến nộp \textit{International Journal of Medical Informatics}}\\[3pt]
{\small\color{elsblue} Dàn trang mô phỏng bố cục bài báo, dùng để đọc và góp ý}\vspace{5pt}}}\\[-1pt]
{\color{elsblue}\rule{\textwidth}{1.6pt}}
\end{center}
\vspace{6pt}
{\raggedright\fontsize{17}{21}\selectfont TITLE\par}
\vspace{4pt}
{\raggedright\large\itshape\color{black!75} GLOSS\par}
\vspace{8pt}
{\large Cong-Danh Tran\textsuperscript{\,a}}\\[3pt]
{\footnotesize\itshape \textsuperscript{a}\,[Đơn vị, Thành phố, Việt Nam]}
\vspace{10pt}

\seclabel{ĐIỂM NỔI BẬT}
\vspace{-2pt}
{\small\begin{itemize}[leftmargin=10pt,itemsep=0pt,topsep=2pt,label=\textbullet]
HIGHLIGHTS
\end{itemize}}
\vspace{8pt}

\noindent\begin{minipage}[t]{0.26\textwidth}
\seclabel{THÔNG TIN BÀI BÁO}
{\footnotesize\raggedright\textit{Từ khóa:}\\
KEYWORDS\par}
\end{minipage}\hfill
\begin{minipage}[t]{0.715\textwidth}
\seclabel{TÓM TẮT}
{\small\setlength{\parskip}{2pt}ABSTRACT\par}
\end{minipage}
\vspace{4pt}
{\color{rulegray}\rule{\textwidth}{0.4pt}}
\vspace{10pt}
}]
\begingroup\renewcommand\thefootnote{}\footnotetext{\textit{Địa chỉ email:} [email] \quad ORCID: [ORCID]}\addtocounter{footnote}{-1}\endgroup
"""
front = (front.replace("TITLE", tex(title)).replace("GLOSS", tex(gloss))
         .replace("HIGHLIGHTS", "\n".join(r"\item " + tex(h) for h in hl))
         .replace("KEYWORDS", r"\\".join(tex(k) for k in keywords))
         .replace("ABSTRACT", "\n\n".join(abstract)))

preamble = r"""\documentclass[9pt,a4paper]{extarticle}
\usepackage[a4paper,top=20mm,bottom=20mm,left=15mm,right=15mm,columnsep=6mm,headsep=5mm]{geometry}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\setsansfont{TeX Gyre Heros}
\setmonofont{DejaVu Sans Mono}[Scale=0.85]
\usepackage{amsmath,amssymb}
\usepackage{graphicx,xcolor,booktabs,tabularx,array,enumitem,fancyhdr,titlesec,caption,microtype}
\usepackage{newunicodechar}
\usepackage[hidelinks]{hyperref}
\usepackage{url}
\urlstyle{same}
\definecolor{elsblue}{HTML}{1F5FA6}
\definecolor{rulegray}{HTML}{9A9A9A}
\definecolor{bandgray}{HTML}{F1F1F1}
\newfontfamily\fallback{DejaVu Serif}[Scale=0.92]
\newunicodechar{−}{\ensuremath{-}}
\newunicodechar{≥}{\ensuremath{\geq}}
\newunicodechar{≤}{\ensuremath{\leq}}
\newunicodechar{∩}{\ensuremath{\cap}}
\newunicodechar{∈}{\ensuremath{\in}}
\newunicodechar{Δ}{\ensuremath{\Delta}}
\newunicodechar{×}{\ensuremath{\times}}
\newunicodechar{α}{\ensuremath{\alpha}}
\newunicodechar{′}{\ensuremath{'}}
\newunicodechar{→}{\ensuremath{\rightarrow}}
\newunicodechar{⇒}{\ensuremath{\Rightarrow}}
\newunicodechar{≈}{\ensuremath{\approx}}
\newunicodechar{²}{\textsuperscript{2}}
\newcommand{\seclabel}[1]{{\fontsize{8}{10}\selectfont\addfontfeatures{LetterSpace=25}\MakeUppercase{#1}}\par\vspace{1pt}{\color{rulegray}\hrule height 0.4pt}\vspace{3pt}}
\newcommand{\tabcap}[2]{{\footnotesize\textbf{Bảng #1}\par\vspace{1pt}#2\par}\vspace{3pt}\scriptsize}
\newcommand{\tabnote}[1]{\par\vspace{2pt}{\scriptsize\raggedright #1\par}}
\newcommand{\figcap}[2]{\par\vspace{3pt}{\footnotesize\raggedright\textbf{Hình #1.} #2\par}}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setcounter{secnumdepth}{-1}
\titleformat{\section}{\normalsize\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{9pt}{4pt}
\titleformat{\subsection}{\normalsize\itshape}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{7pt}{3pt}
\titleformat{\subsubsection}{\small\bfseries}{}{0pt}{}
\setlength{\parindent}{1em}
\setlength{\parskip}{0pt}\setlength{\emergencystretch}{3em}
\setlist{leftmargin=1.4em,itemsep=1pt,topsep=2pt}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\footnotesize C.-D. Tran}
\fancyhead[R]{\footnotesize Bản thảo PLCA-Hypertension (tiếng Việt)}
\fancyfoot[C]{\footnotesize\thepage}
\renewcommand{\headrulewidth}{0pt}
\fancypagestyle{first}{\fancyhf{}\fancyfoot[C]{\footnotesize\thepage}\renewcommand{\headrulewidth}{0pt}}
\setlength{\abovecaptionskip}{2pt}
\renewcommand{\arraystretch}{1.15}
\setlength{\tabcolsep}{3.5pt}
\begin{document}
\thispagestyle{first}
"""

biblio = r"""
\section{Tài liệu tham khảo}
{\scriptsize\raggedright\sloppy
\begin{list}{[\arabic{refc}]}{\usecounter{refc}\setlength{\leftmargin}{2.2em}\setlength{\labelwidth}{2em}\setlength{\itemsep}{0.5pt}\setlength{\parsep}{0pt}}
REFS
\end{list}}
""".replace(r"\bibitem{}", r"\item").replace("REFS", refs_tex.replace(r"\bibitem{}", r"\item"))

doc = preamble.replace(r"\begin{document}", r"\newcounter{refc}" + "\n" + r"\begin{document}") + front + body + biblio + "\n\\end{document}\n"
(ROOT / "paper_vi.tex").write_text(doc, encoding="utf-8")
print("refs:", len(refs), "highlights:", len(hl), "keywords:", len(keywords), "abstract:", len(abstract))
