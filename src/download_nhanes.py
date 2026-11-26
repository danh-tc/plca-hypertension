"""
Download the NHANES XPT files needed for Phase 0 into data/raw/.

Usage:
    python src/download_nhanes.py            # -> data/raw/
    python src/download_nhanes.py --out data/raw --force

Tries the current CDC URL layout first, then the legacy one.
"""
import argparse
import os
import sys
import time
import urllib.request

CYCLES = {"G": ("2011", "2011-2012"), "H": ("2013", "2013-2014"),
          "I": ("2015", "2015-2016"), "J": ("2017", "2017-2018")}
TABLES = ["DEMO", "BPX", "BPQ", "HIQ", "HUQ", "MCQ", "BMX",
          "SMQ", "ALQ", "PAQ", "DIQ", "TCHOL", "GHB"]


def candidate_urls(table, suffix):
    start, span = CYCLES[suffix]
    name = f"{table}_{suffix}"
    return [
        f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{start}/DataFiles/{name}.xpt",
        f"https://wwwn.cdc.gov/Nchs/Nhanes/{span}/{name}.XPT",
    ]


def looks_like_xpt(path):
    with open(path, "rb") as f:
        head = f.read(80)
    return head.startswith(b"HEADER RECORD")


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (plca-hypertension)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("data", "raw"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    failed = []
    for suffix in CYCLES:
        for table in TABLES:
            dest = os.path.join(args.out, f"{table}_{suffix}.XPT")
            if os.path.exists(dest) and not args.force and looks_like_xpt(dest):
                print(f"[skip] {os.path.basename(dest)}")
                continue
            ok = False
            for url in candidate_urls(table, suffix):
                try:
                    fetch(url, dest)
                    if looks_like_xpt(dest):
                        size = os.path.getsize(dest) / 1e6
                        print(f"[ok]   {os.path.basename(dest)}  {size:.1f} MB  <- {url}")
                        ok = True
                        break
                    os.remove(dest)  # got an HTML page instead of data
                except Exception as e:  # noqa: BLE001
                    last = e
                time.sleep(0.5)
            if not ok:
                print(f"[FAIL] {table}_{suffix}")
                failed.append(f"{table}_{suffix}")

    n_all = len(TABLES) * len(CYCLES)
    print(f"\n{n_all - len(failed)}/{n_all} files ready in {args.out}")
    if failed:
        print("Failed:", ", ".join(failed))
        print("Download these manually from https://wwwn.cdc.gov/nchs/nhanes/ and save as <NAME>.XPT")
        sys.exit(1)


if __name__ == "__main__":
    main()
