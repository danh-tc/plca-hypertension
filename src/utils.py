"""Small shared helpers: run manifest."""
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone


def git_sha():
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        return subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def write_manifest(out_dir, args, extra=None):
    from importlib import metadata
    versions = {}
    for dist in ("numpy", "pandas", "scikit-learn", "xgboost", "dice-ml", "dice_ml", "scipy"):
        try:
            versions[dist] = metadata.version(dist)
        except Exception:  # noqa: BLE001
            pass
    man = {"script": os.path.basename(sys.argv[0]), "argv": sys.argv[1:], "args": vars(args),
           "git_sha": git_sha(), "utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": platform.python_version(), "platform": platform.platform(),
           "cpu": platform.processor() or platform.machine(), "cpu_count_logical": os.cpu_count(),
           "versions": versions}
    if extra:
        man.update(extra)
    with open(os.path.join(out_dir, "run_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, default=str)
