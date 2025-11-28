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
### 4. Service Configuration
#### Create Setup Script
```bash
sudo cat > /usr/local/sbin/wlan0-ap-setup.sh << 'EOF'
#!/bin/bash
set -e

MAX_TRIES=10
SLEEP_SEC=1

echo "[wlan0-ap-setup] Waiting for wlan0 to appear..."

for i in $(seq 1 $MAX_TRIES); do
    if /sbin/ip link show wlan0 >/dev/null 2>&1; then
        echo "[wlan0-ap-setup] wlan0 is ready on attempt $i"
        break
    fi
    echo "[wlan0-ap-setup] wlan0 not ready yet (attempt $i/$MAX_TRIES), sleeping ${SLEEP_SE
C}s..."
    sleep "$SLEEP_SEC"
done

if ! /sbin/ip link show wlan0 >/dev/null 2>&1; then
    echo "[wlan0-ap-setup] wlan0 still missing after ${MAX_TRIES} attempts, skipping config
."
    exit 0
fi

/sbin/ip link set wlan0 down || true
/sbin/ip addr flush dev wlan0 || true

/sbin/ip addr add 192.168.4.1/24 dev wlan0 || true
/sbin/ip link set wlan0 up || true

echo "[wlan0-ap-setup] Done."

EOF
sudo chmod +x sudo chmod +x /usr/local/bin/setup-wlan0-static.sh
```
#### setup-wlan0-static.service
```bash
[Unit]
Description=Prepare wlan0 for AP mode (set type, channel, IP)
After=network.target
Before=hostapd.service dnsmasq.service wifi-portal.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/wlan0-ap-setup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```
#### wifi-portal.service
```bash
sudo cat > /etc/systemd/system/wifi-portal.service << 'EOF'
cat /etc/systemd/system/wifi-portal.service
[Unit]
Description=Flask WiFi Captive Portal
After=network.target hostapd.service dnsmasq.service

[Service]
ExecStart=/usr/bin/python3 /userdata/projects/wifi-captive-portal/backend/app.py
WorkingDirectory=/userdata/projects/wifi-captive-portal/backend
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF
```
### 5. Configure Hostapd
cat /etc/systemd/system/hostapd.service
 ```bash
[Unit]
Description=Hostapd WiFi Access Point
Wants=network.target
After=network.target wlan0-ap-setup.service

[Service]
Type=forking
ExecStart=/usr/sbin/hostapd -B /etc/hostapd/hostapd.conf
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo cat > /etc/hostapd/hostapd.conf << 'EOF'
interface=wlan0
driver=nl80211

ssid=NIMBUS-Setup
hw_mode=g
channel=6

ieee80211n=1
wmm_enabled=1
country_code=US

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
no-resolv
log-dhcp

# Captive Portal DNS hijacking
address=/captive.apple.com/192.168.4.1
address=/www.apple.com/192.168.4.1
address=/connectivitycheck.gstatic.com/192.168.4.1
address=/clients3.google.com/192.168.4.1
address=/connectivitycheck.android.com/192.168.4.1
address=/msftconnecttest.com/192.168.4.1
address=/www.msftconnecttest.com/192.168.4.1
EOF
```
### 7. Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable wlan0-ap-setup hostapd dnsmasq wifi-portal
sudo systemctl start wlan0-ap-setup
sudo systemctl start hostapd
sudo systemctl start dnsmasq
sudo systemctl start wifi-portal
```

### 8. Verify Configuration
```bash
cat /etc/systemd/system/botanika-agent.service
[Unit]
Description=Botanika Agent Service
After=network-online.target botanika-keyvault.service
Wants=network-online.target
Requires=botanika-keyvault.service
StartLimitInterval=180s
StartLimitBurst=5

[Service]
Type=notify
ExecStartPre=/bin/bash -c 'until ping -c1 api-botanika-stg.blockifyy.com >/dev/null 2>&1; d
o echo "🔄 Waiting for Internet to reach Botanika API..."; sleep 5; done'
ExecStart=/opt/botanika-agent/botanika-agent
Restart=on-failure
RestartSec=3s
WatchdogSec=30s
WorkingDirectory=/opt/botanika-agent/

[Install]
WantedBy=multi-user.target
```
## Service Verification
### Check Service Status
```bash
sudo systemctl status setup-wlan0-static hostapd dnsmasq wifi-portal --no-pager
```

### Checkmount disk: 
cat /usr/local/bin/auto-prepare-mount.sh

```bash
#!/bin/bash

MOUNTPOINT="/mnt/data"
mkdir -p "$MOUNTPOINT"

DISK=$(lsblk -rno NAME,TYPE | awk '$2=="disk"{print "/dev/"$1}' | head -n 1)
if [ -z "$DISK" ]; then
    echo "No external disk detected!"
    exit 0
fi

echo "🔎 Found disk: $DISK"
PARTITION=$(lsblk -nrpo NAME,TYPE | awk -v d="$DISK" '$2=="part" && index($1,d)==1 {print $
1}' | head -n 1)

if [ -z "$PARTITION" ]; then
    parted --script "$DISK" mklabel gpt
    parted --script "$DISK" mkpart primary ext4 0% 100%
    sleep 2
    
    PARTITION="${DISK}1"
    mkfs.ext4 -F "$PARTITION"
else
    echo "✔ Found partition: $PARTITION"
fi

if mountpoint -q "$MOUNTPOINT"; then
    echo "Already mounted."
else
    echo "Mounting $PARTITION to $MOUNTPOINT ..."
    mount "$PARTITION" "$MOUNTPOINT"
fi

if mountpoint -q "$MOUNTPOINT"; then
    echo "Mounted successfully at $MOUNTPOINT"
else
    echo "Failed to mount!"
    exit 1
fi
```

```bash
cat /etc/systemd/system/auto-mount-data.service
[Unit]
Description=Auto Mount External Hard Drive to /mnt/data
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/auto-mount-data.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo chmod +x /usr/local/bin/auto-mount-data.sh
```

```bash
cat /etc/systemd/network/*.link
[Match]
Type=wlan

[Link]
Name=wlan0
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
sudo journalctl -u setup-wlan0-static -f
sudo journalctl -u setup-wlan0-static -u hostapd -u dnsmasq -u wifi-portal --since "5 minutes ago" --no-pager
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
