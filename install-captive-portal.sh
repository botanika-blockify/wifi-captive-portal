#!/bin/bash
# Full Auto-Setup Script for WiFi Captive Portal
# Run: sudo ./install-captive-portal.sh
# Automatically clones, sets up venv, installs Flask, configures AP

set -e

# === 1. Clone to /userdata (if not already there) ===
if [ ! -d "/userdata/wifi-captive-portal" ]; then
    echo "Cloning repository to /userdata..."
    sudo mkdir -p /userdata
    sudo git clone https://github.com/botanika-blockify/wifi-captive-portal.git /userdata/wifi-captive-portal
fi

cd /userdata/wifi-captive-portal

# === 2. Install System Dependencies ===
echo "Installing system packages..."
sudo apt update
sudo apt install -y hostapd dnsmasq python3-pip python3-venv net-tools iw

# === 3. Setup Virtual Environment + Install Flask ===
echo "Setting up Python virtual environment and installing Flask..."
sudo mkdir -p /userdata/wifi-captive-portal/venv
python3 -m venv /userdata/wifi-captive-portal/venv
/userdata/wifi-captive-portal/venv/bin/pip install --upgrade pip > /dev/null 2>&1
/userdate/wifi-captive-portal/venv/bin/pip install Flask > /dev/null 2>&1

# === 4. Force WiFi Interface to wlan0 (nl80211 + AP support) ===
echo "Detecting and renaming WiFi interface to wlan0..."
WIFI_DEV=$(iw dev | awk '/Interface/ {print $2}' | while read dev; do \
    if iw list | grep -A 20 "Interface $dev" | grep -q "nl80211" && \
       iw list | grep -A 10 "Supported interface modes" | grep -q "AP"; then \
        echo "$dev"; break; \
    fi; \
done)

if [ -n "$WIFI_DEV" ] && [ "$WIFI_DEV" != "wlan0" ]; then
    sudo ip link set dev "$WIFI_DEV" down 2>/dev/null || true
    sudo ip link set dev "$WIFI_DEV" name wlan0 2>/dev/null || true
    sudo ip link set dev wlan0 up
    echo "Renamed $WIFI_DEV to wlan0"
else
    echo "Interface is already wlan0 or no compatible device found"
fi

# === 5. Create IP Setup Script ===
echo "Creating IP setup script..."
sudo tee /usr/local/bin/setup-wlan0-static.sh > /dev/null << 'EOF'
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

# === 6. Create wlan0-static.service ===
echo "Creating wlan0-static.service..."
sudo tee /etc/systemd/system/wlan0-static.service > /dev/null << 'EOF'
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

# === 7. Create wifi-portal.service (using venv) ===
echo "Creating wifi-portal.service with virtual environment..."
sudo tee /etc/systemd/system/wifi-portal.service > /dev/null << 'EOF'
[Unit]
Description=WiFi Captive Portal Backend
After=network.target dnsmasq.service hostapd.service
Wants=dnsmasq.service hostapd.service

[Service]
Type=simple
WorkingDirectory=/userdata/wifi-captive-portal/backend
ExecStart=/userdata/wifi-captive-portal/venv/bin/python /userdata/wifi-captive-portal/backend/app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
User=root
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

# === 8. Hostapd Override ===
echo "Configuring hostapd override..."
sudo mkdir -p /etc/systemd/system/hostapd.service.d
sudo tee /etc/systemd/system/hostapd.service.d/override.conf > /dev/null << 'EOF'
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

# === 9. Configure Hostapd ===
echo "Writing hostapd.conf..."
sudo tee /etc/hostapd/hostapd.conf > /dev/null << 'EOF'
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

# === 10. Configure Dnsmasq ===
echo "Writing dnsmasq.conf..."
sudo tee /etc/dnsmasq.conf > /dev/null << 'EOF'
interface=wlan0
dhcp-range=192.168.4.100,192.168.4.200,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=114.114.114.114
log-dhcp
EOF

# === 11. Enable & Start Services ===
echo "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable wlan0-static hostapd dnsmasq wifi-portal
sudo systemctl restart wlan0-static
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
sudo systemctl restart wifi-portal

# === 12. Final Status ===
echo "Installation complete!"
echo "Services status:"
sudo systemctl status wlan0-static hostapd dnsmasq wifi-portal --no-pager | cat

echo ""
echo "Connect to WiFi: NIMBUS-Setup | Pass: botanika"
echo "Open browser to http://192.168.4.1"