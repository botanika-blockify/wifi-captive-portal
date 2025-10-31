```markdown
# WiFi Captive Portal Setup Guide
A complete WiFi Access Point with captive portal authentication system for embedded devices.
## Requirements
- Linux-based system (tested on Debian/Ubuntu/Embedded Linux)
- WiFi adapter supporting AP mode
- Python 3.7+
- Root access
- Systemd init system
## Quick Installation
```bash
sudo mkdir -p /userdata/wifi-captive-portal && \
sudo git clone https://github.com/botanika-blockify/wifi-captive-portal.git /userdata/wifi-captive-portal && \
sudo chmod +x /userdata/wifi-captive-portal/install-captive-portal.sh && \
sudo /userdata/wifi-captive-portal/install-captive-portal.sh
```
## Munual Installation
### 1. Clone Repository to /userdata
```bash
sudo mkdir -p /userdata
sudo git clone https://github.com/botanika-blockify/wifi-captive-portal.git /userdata/wifi-captive-portal
cd /userdata/wifi-captive-portal
```
### 2. Install Dependencies
```bash
sudo apt update
sudo apt install hostapd dnsmasq python3-pip net-tools iw
pip3 install -r backend/requirements.txt
```
### 3. WiFi Driver Setup
#### Check Your WiFi Hardware
```bash
iw dev
cat /sys/class/net/$(iw dev | grep Interface | cut -d' ' -f2)/device/uevent | grep DRIVER
iw list | grep -A 10 "Supported interface modes" | grep "AP"
```
#### Force nl80211 Interface to wlan0
```bash
WIFI_DEV=$(iw dev | awk '/Interface/ {print $2}' | while read dev; do \
    if iw list | grep -A 20 "Interface $dev" | grep -q "nl80211" && \
       iw list | grep -A 10 "Supported interface modes" | grep -q "AP"; then \
        echo "$dev"; break; \
    fi; \
done)

if [ -n "$WIFI_DEV" ] && [ "$WIFI_DEV" != "wlan0" ]; then
    sudo ip link set dev "$WIFI_DEV" down
    sudo ip link set dev "$WIFI_DEV" name wlan0
    sudo ip link set dev wlan0 up
fi
```
### 4. Service Configuration
#### Create Setup Script
```bash
sudo cat > /usr/local/bin/setup-wlan0-static.sh << 'EOF'
#!/bin/bash
/sbin/ip link set dev wlan0 up
/sbin/ip addr flush dev wlan0
/sbin/ip addr add 192.168.4.1/24 dev wlan0
if ip addr show wlan0 | grep -q "192.168.4.1/24"; then
    exit 0
else
    exit 1
fi
EOF
sudo chmod +x /usr/local/bin/setup-wlan0-static.sh
```
#### wlan0-static.service
```bash
sudo cat > /etc/systemd/system/wlan0-static.service << 'EOF'
[Unit]
Description=Set static IP for wlan0
After=network.target
Before=hostapd.service dnsmasq.service wifi-portal.service
Wants=network.target
[Service]
Type=oneshot
RemainAfterExit=no
Restart=on-failure
RestartSec=3
TimeoutStartSec=300
StartLimitIntervalSec=0
StartLimitBurst=0
ExecStartPre=/bin/bash -c 'if systemctl is-active --quiet NetworkManager; then nmcli dev set wlan0 managed no 2>/dev/null || true; fi'
ExecStartPre=/bin/bash -c 'for i in {1..30}; do [ -e /sys/class/net/wlan0 ] && break; sleep 1; done'
ExecStart=/usr/local/bin/setup-wlan0-static.sh
[Install]
WantedBy=multi-user.target
EOF
```
#### wifi-portal.service
```bash
sudo cat > /etc/systemd/system/wifi-portal.service << 'EOF'
[Unit]
Description=WiFi Captive Portal Backend
After=network.target dnsmasq.service hostapd.service
Wants=dnsmasq.service hostapd.service
[Service]
Type=simple
WorkingDirectory=/userdata/wifi-captive-portal/backend
ExecStart=/usr/bin/python3 /userdata/wifi-captive-portal/backend/app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
User=root
KillMode=process
[Install]
WantedBy=multi-user.target
EOF
```
#### Hostapd Service Override
```bash
sudo mkdir -p /etc/systemd/system/hostapd.service.d
sudo cat > /etc/systemd/system/hostapd.service.d/override.conf << 'EOF'
[Unit]
Description=Override for hostapd - depend on wlan0-static
Requires=wlan0-static.service
After=wlan0-static.service
StartLimitIntervalSec=180
StartLimitBurst=10
[Service]
Type=forking
ExecStartPre=/bin/bash -c 'for i in {1..15}; do ip link show wlan0 | grep -q "state UP" && break; sleep 2; done'
ExecStartPre=/bin/sleep 5
ExecStart=
ExecStart=/usr/sbin/hostapd -B -P /run/hostapd.pid /etc/hostapd/hostapd.conf
Restart=always
RestartSec=3
TimeoutStartSec=45
[Install]
WantedBy=multi-user.target
EOF
```
### 5. Configure Hostapd
```bash
sudo cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=wlan0
driver=nl80211
ssid=NIMBUS-Setup
country_code=US
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=botanika
EOF
sudo chmod 600 /etc/hostapd/hostapd.conf
```
### 6. Configure Dnsmasq
```bash
sudo cat > /etc/dnsmasq.conf << 'EOF'
interface=wlan0
dhcp-range=192.168.4.100,192.168.4.200,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=114.114.114.114
log-dhcp
EOF
```
### 7. Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable wlan0-static hostapd dnsmasq wifi-portal
sudo systemctl start wlan0-static
sudo systemctl start hostapd
sudo systemctl start dnsmasq
sudo systemctl start wifi-portal
```
## Service Verification
### Check Service Status
```bash
sudo systemctl status wlan0-static hostapd dnsmasq wifi-portal --no-pager
```
### Network Verification
```bash
ip -br addr show wlan0
iw dev wlan0 info
cat /var/lib/misc/dnsmasq.leases
curl -I http://192.168.4.1/
```
## Troubleshooting
### Service Diagnostics
```bash
sudo journalctl -u hostapd -f
sudo journalctl -u wifi-portal -f
sudo journalctl -u wlan0-static -f
sudo journalctl -u wlan0-static -u hostapd -u dnsmasq -u wifi-portal --since "5 minutes ago" --no-pager
```
## Reset Script
```bash
sudo /userdata/wifi-captive-portal/reset-to-ap.sh
```
## File Structure
```
wifi-captive-portal/
├── backend/
│   ├── app.py
│   ├── requirements.txt
├── frontend/
│   └── public/
│       ├── logo.png
│       ├── index.html
│       └── success.html
├── reset-to-ap.sh
├── install-captive-portal.sh
└── readme.md
```
## Support
1. Check service status and logs
2. Verify WiFi driver supports AP mode
3. Ensure all dependencies are installed
4. Check NetworkManager isn't interfering
```
```
