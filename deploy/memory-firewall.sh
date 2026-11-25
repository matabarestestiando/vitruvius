#!/bin/sh
set -eu
# Run on vitruvius-memory. Docker published ports bypass conventional INPUT rules.
iptables -C DOCKER-USER -i eth1 -p tcp --dport 8001 ! -s 10.116.0.4 -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -i eth1 -p tcp --dport 8001 ! -s 10.116.0.4 -j DROP
iptables -C DOCKER-USER -i eth0 -p tcp --dport 8001 -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -i eth0 -p tcp --dport 8001 -j DROP
