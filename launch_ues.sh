#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <number_of_ues>"
  exit 1
fi

NUM_UES=$1

BASE_CONFIG="/home/ueransim/UERANSIM/config/open5gs-ue.yaml"
CONFIG_DIR="/home/ueransim/UERANSIM/config"
LOG_DIR="/home/ueransim/UERANSIM/logs"

mkdir -p "$LOG_DIR"

echo "Waiting 10 seconds for gNB and AMF to be ready..."
sleep 10

for i in $(seq 1 $NUM_UES); do
  IMSI="001010000000$(printf "%03d" $i)"
  UE_CONFIG="$CONFIG_DIR/open5gs-ue_$i.yaml"

  echo "Copying $BASE_CONFIG to $UE_CONFIG"
  cp "$BASE_CONFIG" "$UE_CONFIG"

  sed -i "s|supi: 'imsi-001010000000001'|supi: 'imsi-$IMSI'|" "$UE_CONFIG"

  nohup /home/ueransim/UERANSIM/build/nr-ue -c "$UE_CONFIG" > "$LOG_DIR/ue_$i.log" 2>&1 &

  echo "Launched UE $i with IMSI: imsi-$IMSI"
  sleep 1
done

