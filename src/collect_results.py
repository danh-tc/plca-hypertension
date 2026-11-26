"""
Copy the small summary CSVs and run manifests from outputs/ into results/<tag>/ so they can be
committed and checked against the manuscript (raw NHANES data and large per-CF files stay out of git).

    python src/collect_results.py --tag discovery_v3
"""
import argparse
import glob
import os
import shutil

KEEP = ["T1_*.csv", "T1b_*.csv", "T2_*.csv", "T3*.csv", "T5*.csv", "T6_*.csv", "T7_*.csv", "T8_*.csv", "T9*.csv",
        "P1_*.csv", "P2_*.csv", "P3_*.csv", "feature_*.csv", "leak_check_*.csv", "SUMMARY.csv",
        "C0_*.csv", "C1_*.csv", "C2_*.csv", "C3_*.csv", "C4_*.csv", "C5_*.csv", "C6_*.csv", "C7_*.csv",
        "C9_*.csv", "C10_*.csv", "E1_*.csv", "S0_*.csv", "S1_*.csv", "S2_*.csv", "S3_*.csv", "K1_*.csv",
        "run_manifest.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", default="outputs")
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()
    n = 0
    for pat in KEEP:
        for src in glob.glob(os.path.join(args.outputs, "**", pat), recursive=True):
            rel = os.path.relpath(src, args.outputs)
            dst = os.path.join("results", args.tag, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    print(f"copied {n} files to results/{args.tag}/")


if __name__ == "__main__":
    main()
