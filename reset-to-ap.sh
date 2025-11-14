#!/bin/bash
set -e

echo "[*] Delete all saved Wi-Fi connections..."
for c in $(nmcli -t -f NAME connection show | grep -v '^lo$'); do
  if nmcli connection show "$c" 2>/dev/null | grep -q "wifi"; then
    echo "   - Deleting $c"
    nmcli connection delete "$c" || true
  fi
done

echo "[*] Reset wlP2p33s0 to 192.168.4.1/24..."
ip addr flush dev wlP2p33s0 || true
ip addr add 192.168.4.1/24 dev wlP2p33s0
ip link set wlP2p33s0 up || true

echo "[*] Restart services: hostapd, dnsmasq, wifi-portal..."
systemctl restart hostapd || true
systemctl restart dnsmasq || true
systemctl restart wifi-portal || true

echo "[*] Done. Current wlP2p33s0 state:"
ip -br addr show wlP2p33s0

echo "[*] Testing captive portal..."
curl -I http://192.168.4.1/generate_204 || true