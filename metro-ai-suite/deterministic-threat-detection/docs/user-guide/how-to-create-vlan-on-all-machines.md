# Create VLAN on All Machines

To create VLAN interfaces on all Arrow Lake machines, execute the following commands on each machine. This example creates VLANs with IDs 1, 3, and 5, which correspond to the VLAN configuration on the MOXA TSN switch.

Note: Make sure to replace `enp1s0` with the actual network interface name associated with the `i226` network card.

```bash
sudo ip link add link enp1s0 name enp1s0.1 type vlan id 1
sudo ip link set enp1s0.1 type vlan egress-qos-map 0:1
sudo ifconfig enp1s0.1 192.168.127.31 up

sudo ip link add link enp1s0 name enp1s0.3 type vlan id 3
sudo ip link set enp1s0.3 type vlan egress-qos-map 0:3
sudo ifconfig enp1s0.3 192.168.3.31 up

sudo ip link add link enp1s0 name enp1s0.5 type vlan id 5
sudo ip link set enp1s0.5 type vlan egress-qos-map 0:5
sudo ifconfig enp1s0.5 192.168.5.31 up
```

## Instruction to assign vlan id on TSN switch

If you are using MOXA TSN switch, please follow the document [how-to-configure-vlan-on-moxa-switch.md](./how-to-configure-vlan-on-moxa-switch.md) to assign vlan id on TSN switch.
