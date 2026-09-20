#!/bin/sh
# Source only inside an isolated network namespace; shared by spike and production qualification.
setup_network_profile() {
 ip link set lo up
 ip link add d02probe type dummy
 ip addr add 10.201.0.1/24 dev d02probe
 ip link set d02probe up
 ip route add default dev d02probe
 tc qdisc add dev lo root netem limit 1000 delay 50ms 10ms loss 1%
}
