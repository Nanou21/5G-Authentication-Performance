# 5G Authentication Performance

This repository contains scripts and results for comparing the performance of 5G Authentication and Key Agreement (5G-AKA) with Extensible Authentication Protocol for Authentication and Key Agreement (EAP-AKA') in 5G networks.

## Table of Contents

- [Overview](#overview)
- [Setup and Installation](#setup-and-installation)
- [Usage](#usage)
- [Results](#results)
- [Contributing](#contributing)
- [License](#license)

## Overview

The objective is to evaluate and compare their performance in terms of processing time, scalability, and resource utilization.

## SEtup and Installation
The first step is to setup the Open5gs-UERANSIM network.This network was established on two virtual machines on the network '192.68.0.xx'.
This repo does not include the Open5gs setup nor the UERANSIM setup, Check out the [Open5GS repository](https://github.com/open5gs/open5gs) for 5G core network implementation and the [UERANSIM repository](https://github.com/aligungr/UERANSIM).

## Usage
First we begin by choosing the authentication method we want to evaluate, there are two input options allowd by the user '5G_AKA' or 'EAP_AKA'.
The methods can be changed by running [change_authmetod.py](change_authmetod.py) while feeding the authentication method as input
```bash
python3 change_authmetod.py 'Authentication method'
```

Upon a successful network setup, we start the core services by running the shell script [Start services](startservices.sh).
```bash
sudo bash startservices.sh
```
In the UERANSIM start the gnb by running the [start gnb](start_gnb.sh).
Our test was done for 100 User Equipment, hence the 100 subscribers were added in the 5G core by running the [add_subscriber](add_subscribers.py) alongside the desired number of users. 
```bash
# Update package list
sudo python3 add_subscribers.py 100
```
The UEs are started on the UERANSIM side by running the [launch_ues.sh](launch_ues.sh) file, the number specified based on the current test
```bash 
sudo python3 launch_ues.sh <number of ues>

```
The time elapsed per number of ue registration is recorded by by running the script [processing_time.py](processing_time.py) 
```bash 
sudo python3 processing_time.py

```
Like wise for recording the CPU usage run [Memoryusage.py](Memoryusage.py) 
```bash 
sudo python3 Memoryusage.py

```
The above script performs both time and cpu analysis. Thus it can be run to record both time and memory usage. 

The above scripts also saves the results into a csv file : registration_overhead_summary.csv.

Note that upon a complete test for a particular number of UEs the UEs should be stopped before restarting again.

```bash 
nr -pkill ue 
```

Also, for each authentication method, the core is rebuilt hence the services should be stopped then restarted lest we end up with occupied ports.# 5G-Authentication-Performance
Scripts and results for comparing 5G AKA and EAP-AKA’ authentication performance.”
