from pymongo import MongoClient
import sys

# --- Step 1: Accept number of subscribers from CLI ---
if len(sys.argv) != 2:
    print("Usage: python3 add_subscribers.py <number_of_subscribers>")
    sys.exit(1)

try:
    num_subs = int(sys.argv[1])
except ValueError:
    print("Please provide a valid integer.")
    sys.exit(1)

# --- Step 2: Connect to MongoDB ---
client = MongoClient("mongodb://localhost:27017/")
db = client.open5gs
subscribers = db.subscribers

# --- Step 3: Define Base Configuration ---
mcc = "001"
mnc = "01"
key = "465B5CE8B199B49FAA5F0A2EE238A6BC"
opc = "E8ED289DEBA952E4283B54E88E6183CA"
amf = "8000"
imeisv = "4370816125816151"
default_sqn = 97

# --- Step 4: Define QoS and AMBR Settings ---
qos = {
    "arp": {
        "priority_level": 8,
        "pre_emption_capability": 1,
        "pre_emption_vulnerability": 1
    },
    "index": 9
}

ambr = {
    "downlink": {"value": 1, "unit": 3},
    "uplink": {"value": 1, "unit": 3}
}

# --- Step 5: Add Subscribers ---
for i in range(1, num_subs + 1):
    imsi = f"{mcc}{mnc}0000000{i:03d}"

    subscriber = {
        "schema_version": 1,
        "imsi": imsi,
        "msisdn": [],
        "imeisv": imeisv,
        "mme_host": [],
        "mme_realm": [],
        "purge_flag": [],
        "access_restriction_data": 32,
        "subscriber_status": 0,
        "operator_determined_barring": 0,
        "network_access_mode": 0,
        "subscribed_rau_tau_timer": 12,
        "ambr": ambr,
        "security": {
            "k": key,
            "amf": amf,
            "op": None,
            "opc": opc,
            "sqn": default_sqn  # Can also use int(i) if you want unique SQNs
        },
        "slice": [
            {
                "sst": 1,
                "default_indicator": True,
                "session": [
                    {
                        "name": "internet",
                        "type": 3,
                        "qos": qos,
                        "ambr": ambr,
                        "pcc_rule": []
                    }
                ]
            }
        ]
    }

    result = subscribers.update_one({"imsi": imsi}, {"$set": subscriber}, upsert=True)
    print(f"✅ Added/Updated subscriber: {imsi}")

  
