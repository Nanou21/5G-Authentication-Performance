import psutil
import time
import re
import subprocess
import threading
from datetime import datetime
from collections import defaultdict
import csv
from pathlib import Path

CSV_FILE = "registration_overhead_summary.csv"

LOG_FILE = "amf.log"
SAMPLING_INTERVAL = 0.1  # seconds

samples = []  # List of (timestamp, cpu%, mem%)
sampling = True
ue_windows = defaultdict(lambda: {"start": None, "end": None})


def get_amf_pid():
    try:
        output = subprocess.check_output(["pgrep", "-f", "open5gs-amfd"])
        return int(output.decode().strip())
    except subprocess.CalledProcessError:
        print("[ERROR] AMF process not found.")
        exit(1)


def sample_amf_usage(proc):
    """Continuously sample CPU/memory while 'sampling' is True."""
    while sampling:
        try:
            ts = datetime.now()
            cpu = proc.cpu_percent(interval=None)
            mem = proc.memory_info().rss / (1024 * 1024)  # MB
            samples.append((ts, cpu, mem))
            time.sleep(SAMPLING_INTERVAL)
        except psutil.NoSuchProcess:
            print("[WARN] AMF exited during sampling.")
            break


def monitor_log(num_expected_ues):
    """Watch log to detect start/complete times for multiple UEs."""
    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)  # Jump to end

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
                if not ue_windows[ue]["start"]:
                    ue_windows[ue]["start"] = ts
                    print(f"[INFO] Registration started for UE-{ue}")

            if imsi_match and "Registration complete" in line:
                ue = imsi_match.group(1)
                if not ue_windows[ue]["end"]:
                    ue_windows[ue]["end"] = ts
                    print(f"[INFO] Registration complete for UE-{ue}")

            registered_ues = [ue for ue in ue_windows if ue_windows[ue]["start"] and ue_windows[ue]["end"]]
            if len(registered_ues) >= num_expected_ues:
                print(f"[INFO] All {num_expected_ues} UEs registered. Stopping.")
                break


def analyze_per_ue():
    print("\n--- Registration Overhead Per UE ---")
    all_start_times = []
    all_end_times = []

    for ue, window in ue_windows.items():
        start, end = window["start"], window["end"]
        if not start or not end:
            print(f"UE-{ue}: Incomplete registration data.")
            continue

        window_samples = [s for s in samples if start <= s[0] <= end]
        if not window_samples:
            print(f"UE-{ue}: No samples recorded.")
            continue

        cpu_avg = sum(s[1] for s in window_samples) / len(window_samples)
        mem_avg = sum(s[2] for s in window_samples) / len(window_samples)
        duration = (end - start).total_seconds()

        all_start_times.append(start)
        all_end_times.append(end)

        print(f"UE-{ue} | Time: {duration:.2f}s | Avg CPU: {cpu_avg:.2f}% | Avg Mem: {mem_avg:.2f} MB")

    # ✅ Calculate global average for combined registration period
    if all_start_times and all_end_times:
        global_start = min(all_start_times)
        global_end = max(all_end_times)
        global_samples = [s for s in samples if global_start <= s[0] <= global_end]

        if global_samples:
            cpu_global_avg = sum(s[1] for s in global_samples) / len(global_samples)
            mem_global_avg = sum(s[2] for s in global_samples) / len(global_samples)
            global_duration = (global_end - global_start).total_seconds()

            print("\n--- Overall Combined Overhead ---")
            print(f"Total Time: {global_duration:.2f}s")
            print(f"Avg CPU Usage (All UEs): {cpu_global_avg:.2f}%")
            print(f"Avg Memory Usage (All UEs): {mem_global_avg:.2f} MB")
        else:
            print("\n[WARN] No global samples found in overall UE window.")
                  # ✅ Append results to CSV
    headers = [
        "timestamp", "num_UEs", "total_time_sec",
        "avg_CPU_percent", "avg_memory_MB"
    ]
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        len(ue_windows),
        round(global_duration, 2),
        round(cpu_global_avg, 2),
        round(mem_global_avg, 2)
    ]

    write_headers = not Path(CSV_FILE).exists()
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if write_headers:
            writer.writerow(headers)
        writer.writerow(row)

    print(f"[INFO] Summary saved to: {CSV_FILE}")


def main():
    global sampling

    try:
        num_expected_ues = int(input("Enter number of UEs to monitor: "))
        if num_expected_ues <= 0:
            raise ValueError
    except ValueError:
        print("[ERROR] Please enter a valid positive integer.")
        return

    amf_pid = get_amf_pid()
    if not psutil.pid_exists(amf_pid):
        print(f"[ERROR] AMF PID {amf_pid} not running.")
        exit(1)

    amf_proc = psutil.Process(amf_pid)

    # Prime CPU sampling
    amf_proc.cpu_percent(interval=None)

    # Start sampling thread
    sampler_thread = threading.Thread(target=sample_amf_usage, args=(amf_proc,))
    sampler_thread.start()

    # Give time to warm up
    time.sleep(0.5)

    # Monitor log until all UEs are done
    monitor_log(num_expected_ues)

    # Stop sampling
    sampling = False
    sampler_thread.join()

    # Analyze
    analyze_per_ue()


if __name__ == "__main__":
    main()

