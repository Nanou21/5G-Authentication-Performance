#!/usr/bin/env python3

import psutil
import time
import re
import subprocess
import threading
from datetime import datetime
from collections import defaultdict
import csv
from pathlib import Path
import argparse
import signal
import sys
import os

# =========================
# Globals
# =========================
CSV_FILE = None
LOG_FILE = None
SAMPLING_INTERVAL = 0.1

samples = []
sampling = True
stop_event = threading.Event()

# UE -> {start, end}
ue_windows = defaultdict(lambda: {"start": None, "end": None})


# =========================
# Signal handling
# =========================
def _handle_signal(signum, frame):
    global sampling
    sampling = False
    stop_event.set()

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# =========================
# AMF PID
# =========================
def get_amf_pid():
    try:
        output = subprocess.check_output(["pgrep", "-f", "open5gs-amfd"])
        return int(output.decode().strip())
    except subprocess.CalledProcessError:
        print("[ERROR] AMF process not found.")
        sys.exit(1)


# =========================
# CPU + memory sampler
# =========================
def sample_amf_usage(proc):
    proc.cpu_percent(interval=None)  # prime
    while sampling and not stop_event.is_set():
        try:
            ts = datetime.now()
            cpu = proc.cpu_percent(interval=SAMPLING_INTERVAL)
            mem = proc.memory_info().rss / (1024 * 1024)  # MB
            samples.append((ts, cpu, mem))
        except psutil.NoSuchProcess:
            break


# =========================
# Log monitor (UE windows)
# =========================
def monitor_log(num_expected_ues):
    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)  # tail

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue

            ts = datetime.now()

            suci_match = re.search(r"suci-[\d\-]+(\d{6})", line)
            imsi_match = re.search(r"imsi-\d+(\d{6})", line)

            if suci_match:
                ue = suci_match.group(1)
                if ue_windows[ue]["start"] is None:
                    ue_windows[ue]["start"] = ts

            if imsi_match and "Registration complete" in line:
                ue = imsi_match.group(1)
                if ue_windows[ue]["end"] is None:
                    ue_windows[ue]["end"] = ts

            completed = [
                ue for ue in ue_windows
                if ue_windows[ue]["start"] and ue_windows[ue]["end"]
            ]

            if len(completed) >= num_expected_ues:
                print(f"[INFO] All {num_expected_ues} UEs registered.")
                break


# =========================
# Analysis + CSV writing
# =========================
def analyze_and_write():
    if not samples:
        print("[WARN] No CPU/memory samples collected.")
        return

    per_ue_rows = []
    all_start_times = []
    all_end_times = []

    # ---- Per-UE registration time ----
    for ue, window in ue_windows.items():
        start, end = window["start"], window["end"]
        if not start or not end:
            continue

        duration = (end - start).total_seconds()
        per_ue_rows.append((ue, start, end, round(duration, 3)))
        all_start_times.append(start)
        all_end_times.append(end)

    if not per_ue_rows:
        print("[WARN] No complete UE registration windows.")
        return

    # ---- Average per-UE registration time (KEY METRIC) ----
    avg_ue_time = sum(r[3] for r in per_ue_rows) / len(per_ue_rows)

    # ---- Global window (system behavior) ----
    global_start = min(all_start_times)
    global_end = max(all_end_times)
    global_duration = (global_end - global_start).total_seconds()

    global_samples = [
        s for s in samples if global_start <= s[0] <= global_end
    ]

    if not global_samples:
        print("[WARN] No samples inside global window.")
        return

    cpu_avg = sum(s[1] for s in global_samples) / len(global_samples)
    mem_avg = sum(s[2] for s in global_samples) / len(global_samples)

    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)

    # =========================
    # Summary CSV (USED BY ORCHESTRATOR)
    # =========================
    summary_headers = [
        "timestamp",
        "num_UEs",
        "total_time_sec",
        "avg_ue_registration_time_sec",
        "avg_CPU_percent",
        "avg_memory_MB"
    ]

    summary_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        len(per_ue_rows),
        round(global_duration, 3),
        round(avg_ue_time, 3),
        round(cpu_avg, 2),
        round(mem_avg, 2)
    ]

    write_header = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(summary_headers)
        writer.writerow(summary_row)
        f.flush()
        os.fsync(f.fileno())

    print(f"[INFO] Summary written to {CSV_FILE}")

    # =========================
    # Per-UE CSV (DETAILED ANALYSIS)
    # =========================
    per_ue_csv = CSV_FILE.with_name(CSV_FILE.stem + "_per_ue.csv")

    with open(per_ue_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "UE",
            "registration_start",
            "registration_end",
            "registration_time_sec"
        ])
        for row in per_ue_rows:
            writer.writerow(row)

    print(f"[INFO] Per-UE registration times written to {per_ue_csv}")


# =========================
# Main
# =========================
def main():
    global CSV_FILE, LOG_FILE, SAMPLING_INTERVAL, sampling
    global samples, ue_windows

    samples = []
    ue_windows = defaultdict(lambda: {"start": None, "end": None})

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--num-ues", type=int, required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--interval", type=float, default=0.1)
    args = parser.parse_args()

    CSV_FILE = Path(args.output)
    LOG_FILE = args.log
    SAMPLING_INTERVAL = args.interval

    amf_proc = psutil.Process(get_amf_pid())

    sampler = threading.Thread(
        target=sample_amf_usage,
        args=(amf_proc,),
        daemon=True
    )
    sampler.start()

    time.sleep(0.2)

    monitor_log(args.num_ues)

    sampling = False
    stop_event.set()
    sampler.join(timeout=2.0)

    analyze_and_write()


if __name__ == "__main__":
    main()
