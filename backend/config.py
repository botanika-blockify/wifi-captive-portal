import os

class Config:
    WIFI_IFACE = "wlan0"
    VIRTUAL_IFACE = "wlan1"
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
    
    MAX_CONNECTION_ATTEMPTS = 1
    CONNECTION_TIMEOUT = 30
    SCAN_TIMEOUT = 10
    
    AP_SSID = "NIMBUS-Setup"
    AP_PASSWORD = "botanika"
    AP_CHANNEL = 6
    AP_IP = "192.168.4.1"
    AP_NETMASK = "255.255.255.0"
    DHCP_RANGE = "192.168.4.100,192.168.4.200"