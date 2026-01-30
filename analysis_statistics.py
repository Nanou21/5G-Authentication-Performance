#!/usr/bin/env python3
import subprocess
import os
import io
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# =========================
# REMOTE CORE CONFIG
# =========================
REMOTE_USER = "gcore1"
REMOTE_HOST = "192.168.0.6"
SSH_KEY = os.path.expanduser("~/.ssh/id_rsa")
REMOTE_RESULTS_DIR = "/home/gcore1/open5gs/5G-Authentication-Performance/results"

# =========================
# SSH HELPERS
# =========================
def ssh_cmd(cmd):
    full = f'ssh -i "{SSH_KEY}" -o StrictHostKeyChecking=no {REMOTE_USER}@{REMOTE_HOST} "{cmd}"'
    return subprocess.run(full, shell=True, capture_output=True, text=True)

def read_remote_csv(path):
    res = ssh_cmd(f"cat {path}")
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return pd.read_csv(io.StringIO(res.stdout))

# =========================
# LOAD ALL PER-UE FILES
# =========================
print("[INFO] Discovering per-UE CSV files on remote core...")

find_cmd = (
    f'find {REMOTE_RESULTS_DIR} '
    f'-type f -name "*_per_ue.csv" -size +0c'
)

res = ssh_cmd(find_cmd)
if res.returncode != 0 or not res.stdout.strip():
    raise RuntimeError("No per-UE CSV files found on remote core")

remote_files = [f.strip() for f in res.stdout.splitlines()]
print(f"[INFO] Found {len(remote_files)} per-UE files")

records = []

for path in remote_files:
    filename = os.path.basename(path)

    # Expected:
    # 5G_AKA_10ues_iter3_registration_overhead_summary_per_ue.csv
    try:
        # Remove known suffix
        stem = filename.replace(
            "_registration_overhead_summary_per_ue.csv", ""
        )

        # Example stem:
        # 5G_AKA_70ues_iter9

        # ---- Extract iteration ----
        stem_no_iter, iter_part = stem.rsplit("iter", 1)
        iteration = int(iter_part)

        # stem_no_iter now ends with "_70ues"
        stem_no_iter = stem_no_iter.rstrip("_")

        # ---- Extract UE count ----
        pre_auth, ue_part = stem_no_iter.rsplit("_", 1)
        ue_count = int(ue_part.replace("ues", ""))

        # ---- Remaining is auth method (may contain underscores) ----
        auth_method = pre_auth

    except Exception as e:
        print(f"[WARN] Skipping malformed filename: {filename} ({e})")
        continue



    df = read_remote_csv(path)
    if df is None or df.empty:
        continue

    df["auth_method"] = auth_method
    df["ue_count"] = ue_count
    df["iteration"] = iteration

    records.append(df)

if not records:
    raise RuntimeError("Per-UE CSVs found, but none could be loaded")

all_ues = pd.concat(records, ignore_index=True)

print("[INFO] Loaded per-UE records:", len(all_ues))

# =========================
# STATISTICS HELPERS
# =========================
def mean_ci(x, confidence=0.95):
    x = np.array(x, dtype=float)
    mean = x.mean()
    sem = stats.sem(x)
    ci = stats.t.interval(confidence, len(x)-1, loc=mean, scale=sem)
    return mean, ci

# =========================
# PER-AUTH-METHOD STATS
# =========================
summary = []

for auth in sorted(all_ues["auth_method"].unique()):
    subset = all_ues[all_ues["auth_method"] == auth]
    mean, ci = mean_ci(subset["registration_time_sec"])
    summary.append({
        "auth_method": auth,
        "mean_registration_time_sec": mean,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "num_samples": len(subset)
    })

summary_df = pd.DataFrame(summary)
summary_df.to_csv("auth_method_summary_stats.csv", index=False)

print("\n=== Per-Authentication-Method Statistics ===")
print(summary_df)

# =========================
# FORMAL COMPARISON
# =========================
aka = all_ues[all_ues["auth_method"] == "5G_AKA"]["registration_time_sec"]
eap = all_ues[all_ues["auth_method"] == "EAP_AKA"]["registration_time_sec"]

mean_diff = aka.mean() - eap.mean()
diff_ci = stats.t.interval(
    0.95,
    len(aka)+len(eap)-2,
    loc=mean_diff,
    scale=np.sqrt(aka.var()/len(aka) + eap.var()/len(eap))
)

t_stat, p_value = stats.ttest_ind(aka, eap, equal_var=False)

comparison = {
    "mean_difference_sec": mean_diff,
    "ci_low": diff_ci[0],
    "ci_high": diff_ci[1],
    "t_statistic": t_stat,
    "p_value": p_value
}

pd.DataFrame([comparison]).to_csv("aka_vs_eap_comparison.csv", index=False)

print("\n=== Formal Comparison: 5G-AKA vs EAP-AKA ===")
for k, v in comparison.items():
    print(f"{k}: {v}")

# =========================
# PAPER-QUALITY PLOTS
# =========================
plt.figure(figsize=(8,6))
plt.bar(
    summary_df["auth_method"],
    summary_df["mean_registration_time_sec"],
    yerr=[
        summary_df["mean_registration_time_sec"] - summary_df["ci_low"],
        summary_df["ci_high"] - summary_df["mean_registration_time_sec"]
    ],
    capsize=8
)

plt.ylabel("Average UE Registration Time (s)")
plt.xlabel("Authentication Method")
plt.title("UE Registration Time with 95% Confidence Intervals")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("registration_time_ci.png", dpi=300)
plt.close()

print("\n[INFO] Analysis complete.")
print("[INFO] Files generated:")
print("  • auth_method_summary_stats.csv")
print("  • aka_vs_eap_comparison.csv")
print("  • registration_time_ci.png")
