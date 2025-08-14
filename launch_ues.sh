#!/bin/bash

# Read the number of UEs from command-line input
if [ -z "$1" ]; then
  echo "Usage: $0 <number_of_ues>"
  exit 1
fi

NUM_UES=$1

# Ensure logs directory exists
mkdir -p logs

for i in $(seq 1 $NUM_UES); do
  IMSI="001010000000$(printf "%03d" $i)"  # e.g., imsi-208930000000001

  # Copy base config and modify IMSI
  cp config/open5gs-ue.yaml config/open5gs-ue_$i.yaml
  sed -i "s|supi: 'imsi-001010000000001'|supi: 'imsi-$IMSI\'|" config/open5gs-ue_$i.yaml

  # Run the UE in the background
  ./build/nr-ue -c config/open5gs-ue_$i.yaml > logs/ue_$i.log 2>&1 &

  echo "Generated config/open5gs-ue_$i.yaml with IMSI: imsi-$IMSI"
 # sudo tail -f  logs/ue_$i.log	
  sleep 0.2  # avoid overwhelming the system
done

