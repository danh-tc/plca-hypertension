"""Record the computational environment and SHA-256 checksums of the raw NHANES files.
Run at the start of the analysis:
    python scripts/record_environment.py data/raw environment.json
"""
import hashlib, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from importlib import metadata

data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
out = sys.argv[2] if len(sys.argv) > 2 else "environment.json"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

files = {}
for root, _, names in os.walk(data_dir):
    for n in sorted(names):
        p = os.path.join(root, n)
        files[os.path.relpath(p, data_dir).replace("\\", "/")] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}
try:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
except Exception:  # noqa: BLE001
    sha = "unknown"
pkgs = {d.metadata["Name"]: d.version for d in metadata.distributions()}
env = {"utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": sha,
       "python": platform.python_version(), "platform": platform.platform(),
       "cpu": platform.processor() or platform.machine(), "cpu_count_logical": os.cpu_count(),
       "packages": dict(sorted(pkgs.items(), key=lambda kv: kv[0].lower())),
       "data_dir": data_dir, "n_data_files": len(files), "data_files": files}
with open(out, "w", encoding="utf-8") as f:
    json.dump(env, f, indent=2)
print(f"wrote {out}: {len(files)} data files, python {env['python']}, {env['platform']}, git {sha[:7]}")
