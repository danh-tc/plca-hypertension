"""Builds the IJMI first-submission package (LaTeX route) into submission/IJMI_R0/.

    python submission/build_package.py            # final: stops if any [placeholder] remains
    python submission/build_package.py --draft    # builds anyway and lists the placeholders

Steps: rebuild manuscript (paper/en/build_els.py submission), copy the .tex with figures renamed
Figure_1.pdf ... Figure_4.pdf and Figure_A1.pdf, compile it inside the package to prove it builds
standalone, write Highlights.docx, Cover_Letter.pdf, rebuild the checklists, check the IJMI limits,
and write README.md (internal, not for upload). Experiments and results are not touched.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "paper" / "en"
OUT = ROOT / "submission" / "IJMI_R0"
DRAFT = "--draft" in sys.argv
EXPERIMENT_COMMIT = "85a813b"
FIGS = {"fig1.pdf": "Figure_1.pdf", "fig2.pdf": "Figure_2.pdf", "fig3.pdf": "Figure_3.pdf",
        "fig4.pdf": "Figure_4.pdf", "figA1.pdf": "Figure_A1.pdf"}


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pdflatex(tex, cwd):
    for _ in range(2):
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex], cwd=cwd,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode:
            sys.exit(f"[ERROR] {tex} does not compile:\n" + r.stdout[-2000:])


# 1. manuscript
run([sys.executable, "build_els.py", "submission"], EN)
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
tex = (EN / "paper_en_submission.tex").read_text(encoding="utf-8")
for old, new in FIGS.items():
    tex = tex.replace("{" + old + "}", "{" + new + "}")
    shutil.copy(EN / old, OUT / new)
(OUT / "Manuscript.tex").write_text(tex, encoding="utf-8")
pdflatex("Manuscript.tex", OUT)

# 2. checks
src = {p: (EN / p).read_text(encoding="utf-8") for p in ("front_src.md", "body_src.md", "back_src.md", "appendix_src.md")}
words = int(subprocess.check_output([sys.executable, "wordcount.py", "body_src.md"], cwd=EN).decode())
abstract = src["front_src.md"].split("## Abstract")[1].split("**Keywords")[0]
abs_words = len(re.findall(r"[A-Za-z0-9][\w'’./–−-]*", abstract.replace("**", "")))
highlights = re.findall(r"^- (.*)$", src["front_src.md"].split("## Abstract")[0], re.M)
keywords = [k for k in re.search(r"\*\*Keywords:\*\*\s*(.*)", src["front_src.md"]).group(1).split(";") if k.strip()]
n_tab = len(re.findall(r"^\*\*Table \d+\.\*\*", src["body_src.md"], re.M))
n_fig = len(re.findall(r"^!\[Fig\. \d+\.", src["body_src.md"], re.M))
checks = [("Main text words", words, words <= 3000, "<= 3000"),
          ("Abstract words", abs_words, abs_words <= 300, "<= 300"),
          ("Figures (main)", n_fig, n_fig <= 4, "<= 4"),
          ("Tables (main)", n_tab, n_tab <= 5, "<= 5"),
          ("Keywords", len(keywords), 1 <= len(keywords) <= 7, "1-7"),
          ("Highlights", len(highlights), 3 <= len(highlights) <= 5, "3-5"),
          ("Longest highlight (chars)", max(map(len, highlights)), max(map(len, highlights)) <= 85, "<= 85")]
placeholders = sorted({m for s in src.values() for m in re.findall(r"\[(?:To be|Author|DOI to be)[^\]]*\]", s)})
bad = [c for c in checks if not c[2]]
if bad:
    sys.exit(f"[ERROR] IJMI limits not met: {bad}")
if placeholders and not DRAFT:
    sys.exit("[ERROR] placeholders remain (use --draft to build anyway):\n  " + "\n  ".join(placeholders))

# 3. highlights (separate editable file, 'highlights' in the file name)
import docx  # noqa: E402
d = docx.Document()
d.add_heading("Highlights", level=1)
for h in highlights:
    d.add_paragraph(h, style="List Bullet")
d.save(OUT / "Highlights.docx")

# 4. cover letter
cl = (ROOT / "submission" / "templates" / "cover_letter.tex").read_text(encoding="utf-8")
cl = cl.replace(r"\WORDS{}", f"{words:,}")
tmp = OUT / "_cl"
tmp.mkdir()
(tmp / "Cover_Letter.tex").write_text(cl, encoding="utf-8")
pdflatex("Cover_Letter.tex", tmp)
shutil.copy(tmp / "Cover_Letter.pdf", OUT / "Cover_Letter.pdf")
shutil.rmtree(tmp)

# 5. checklists
run([sys.executable, "build_checklists.py"], ROOT / "submission" / "checklists")
for f in ("IJMEDI_ML_Checklist.pdf", "TRIPOD_AI_Checklist.pdf"):
    shutil.copy(ROOT / "submission" / "checklists" / f, OUT / f)

# 6. tidy and README
for p in OUT.glob("Manuscript.*"):
    if p.suffix not in (".tex", ".pdf"):
        p.unlink()
sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
pages = subprocess.check_output(["pdfinfo", str(OUT / "Manuscript.pdf")]).decode()
pages = re.search(r"Pages:\s+(\d+)", pages).group(1)
lines = ["# IJMI first submission (R0) - internal notes, do not upload", "",
         f"- Built from repository commit `{sha}`; endpoint results from experiment commit `{EXPERIMENT_COMMIT}`.",
         "- Build: `python submission/build_package.py` (LaTeX route; elsarticle preprint, review, 12 pt, line numbers).",
         f"- Manuscript.pdf: {pages} pages (preview only; Manuscript.tex is the source file).", "",
         "## Limits", "", "| Check | Value | Limit | OK |", "|---|---|---|---|"]
lines += [f"| {a} | {b} | {d_} | {'yes' if c else 'NO'} |" for a, b, c, d_ in checks]
lines += ["", "## Upload list (Editorial Manager item type in brackets)", "",
          "1. Manuscript.tex [Manuscript, LaTeX source] + Manuscript.pdf [reference PDF, if requested]",
          "2. Figure_1.pdf ... Figure_4.pdf [Figure]; Figure_A1.pdf [Supplementary figure; also embedded in Appendix A]",
          "3. Highlights.docx [Highlights]",
          "4. IJMEDI_ML_Checklist.pdf [mandatory ML checklist]; TRIPOD_AI_Checklist.pdf [reporting checklist]",
          "5. Cover_Letter.pdf [Cover letter]",
          "6. Declaration of interest: generate with the Elsevier Declarations Tool and upload the Word file it produces "
          "(not produced here).", "",
          "## Open items", ""]
lines += [f"- {p}" for p in placeholders] or ["- none"]
(OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nPackage: {OUT}")
