import re
from datetime import datetime
from collections import defaultdict

log_file = "amf.log"

# Store timestamps by UE last 6 digits
log_timestamps = defaultdict(lambda: {"start": None, "complete": None})

with open(log_file, "r") as f:
    for line in f:
        # Extract timestamp
        timestamp_match = re.match(r"(\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{3})", line)
        if not timestamp_match:
            continue
        timestamp_str = timestamp_match.group(1)
        timestamp = datetime.strptime(timestamp_str, "%m/%d %H:%M:%S.%f")

        # Check for SUCI or IMSI
        suci_match = re.search(r"suci-[\d\-]+(\d{6})", line)   # Last 6 digits
        imsi_match = re.search(r"imsi-\d+(\d{6})", line)       # Last 6 digits

        # START time: when SUCI first appears
        if suci_match:
            ue_suffix = suci_match.group(1)
            if not log_timestamps[ue_suffix]["start"]:
                log_timestamps[ue_suffix]["start"] = timestamp
                continue  # Skip to next line

        # COMPLETE time: when IMSI and "Registration complete" appear
        if imsi_match and "Registration complete" in line:
            ue_suffix = imsi_match.group(1)
            if not log_timestamps[ue_suffix]["complete"]:
                log_timestamps[ue_suffix]["complete"] = timestamp

# Match start and complete times by UE suffix
per_ue_times = []

for ue_suffix, times in log_timestamps.items():
    start = times["start"]
    complete = times["complete"]

    if start and complete:
        delta = complete - start
        seconds = delta.total_seconds()
        per_ue_times.append(seconds)
        print(f"UE ending with {ue_suffix}: Registration time = {seconds:.3f} seconds")
    else:
        print(f"UE ending with {ue_suffix}: Incomplete data (start or complete time missing)")

# Average time across UEs
if per_ue_times:
    avg_time = sum(per_ue_times) / len(per_ue_times)
    print(f"\nAverage registration time per UE: {avg_time:.3f} seconds")
else:
    print("No complete UE registrations found.")

