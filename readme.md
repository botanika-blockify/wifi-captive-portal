# Wi-Fi Captive Portal

A simple and elegant Wi-Fi captive portal for embedded devices that allows users to connect to available Wi-Fi networks through a web interface.

## Features

- **Automatic Network Scanning**: Automatically scans and displays available Wi-Fi networks
- **Signal Strength Indicators**: Visual signal strength bars for each network
- **Secure Connection**: Supports both open and password-protected networks
- **Responsive Design**: Modern dark theme UI that works on mobile and desktop
- **Captive Portal Detection**: Handles captive portal detection from various devices
- **Success Confirmation**: Redirects to success page after successful connection

## Project Structure

```
wifi-captive-portal/
├── app.py                 # Flask backend server
├── frontend/
│   ├── index.html         # Main portal interface
│   ├── success.html       # Success confirmation page
│   └── public/
│       └── logo.png       # Brand logo
└── README.md
```

## Requirements

- Python 3.x
- Flask
- NetworkManager (nmcli)
- systemd (for service management)

## Installation

1. **Clone or download the project files**

   ```bash
   cd /userdata/wifi-captive-portal
   ```

2. **Install Python dependencies**

   ```bash
   pip install flask
   ```

3. **Set up systemd service** (create `/etc/systemd/system/wifi-portal.service`)

   ```ini
   [Unit]
   Description=Wi-Fi Captive Portal
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/userdata/wifi-captive-portal
   ExecStart=/usr/bin/python3 /userdata/wifi-captive-portal/app.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable and start the service**
   ```bash
   systemctl daemon-reload
   systemctl enable wifi-portal
   systemctl start wifi-portal
   ```

## Configuration

### Network Interface

By default, the portal uses `wlan0`. To change this, edit the `WIFI_IFACE` variable in `app.py`:

```python
WIFI_IFACE = "wlan0"
```

### Port

The portal runs on port 80 by default. To change this, modify the `app.run()` call in `app.py`:

```python
app.run(host="0.0.0.0", port=80)
```

## Usage

### Starting the Portal

```bash
systemctl start wifi-portal
```

### Stopping the Portal

```bash
systemctl stop wifi-portal
```

### Restarting the Portal

```bash
systemctl restart wifi-portal
```

### Checking Status

```bash
systemctl status wifi-portal
```

### Viewing Logs

```bash
journalctl -u wifi-portal -f
```

## API Endpoints

- `GET /api/scan` - Scan for available Wi-Fi networks
- `POST /api/connect` - Connect to a Wi-Fi network
- `GET /api/status` - Check connection status
- `GET /success.html` - Success confirmation page

## Captive Portal Support

The portal handles captive portal detection requests from:

- iOS/macOS (`/generate_204`, `/hotspot-detect.html`)
- Android (`/generate_204`)
- Windows (`/ncsi.txt`, `/connecttest.txt`)
- Various browsers and devices

## Troubleshooting

### Common Issues

1. **Portal not starting**

   - Check if port 80 is available
   - Verify Python and Flask are installed
   - Check service logs: `journalctl -u wifi-portal`

2. **No networks found**

   - Ensure wireless interface is up: `ip link show wlan0`
   - Check if NetworkManager is running: `systemctl status NetworkManager`

3. **Connection failures**
   - Verify SSID and password are correct
   - Check if network is in range
   - Look for error details in logs

### Testing API Manually

```bash
# Test network scanning
curl http://localhost/api/scan

# Test connection
curl -X POST http://localhost/api/connect \
  -H "Content-Type: application/json" \
  -d '{"ssid":"YOUR_SSID","password":"YOUR_PASSWORD"}'
```

## Customization

### Changing Branding

- Replace `frontend/public/logo.png` with your logo
- Modify colors in CSS (look for `#f28c38` orange theme)

### Modifying UI Text

Edit text content in:

- `frontend/index.html` - Main portal interface
- `frontend/success.html` - Success page

### Styling Changes

CSS styles are embedded in each HTML file. Key color variables:

- Primary orange: `#f28c38`
- Background: `#181c20`
- Card background: `#23272b`
- Text: `#ffffff`
- Muted text: `#a0a6b0`

## Security Notes

- The portal runs on the local network only
- Passwords are transmitted over local network
- Consider using HTTPS for production deployments
- The service runs as root to manage network connections

## Support

For issues and questions:

1. Check service logs: `journalctl -u wifi-portal`
2. Verify network interface configuration
3. Test API endpoints manually
4. Ensure all dependencies are installed

---

**Note**: This captive portal is designed for local network use and should be properly secured for production environments.
