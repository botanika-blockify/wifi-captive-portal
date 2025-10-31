import subprocess
import time
import logging
from utils import run_command

class VirtualAPManager:
    def __init__(self, physical_iface="wlan0", virtual_iface="wlan1"):
        self.physical_iface = physical_iface
        self.virtual_iface = virtual_iface
        self.virtual_ap_conf = "/etc/hostapd/hostapd_virtual.conf"
        
    def create_virtual_interface(self):
        """Tạo virtual interface cho AP mode"""
        try:
            run_command(f"iw dev {self.virtual_iface} del", timeout=5)
            time.sleep(1)
            
            code, out, err = run_command(f"iw phy {self.physical_iface} interface add {self.virtual_iface} type __ap", timeout=10)
            if code != 0:
                logging.error(f"Failed to create virtual interface: {err}")
                return False
                
            time.sleep(2)
            
            run_command(f"ip link set {self.virtual_iface} up", timeout=5)
            time.sleep(1)
            
            run_command(f"ifconfig {self.virtual_iface} 192.168.4.1 netmask 255.255.255.0 up", timeout=5)
            
            logging.info(f"Virtual interface {self.virtual_iface} created successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error creating virtual interface: {e}")
            return False
    
    def create_virtual_hostapd_config(self):
        """Tạo config hostapd cho virtual interface"""
        config_content = f"""interface={self.virtual_iface}
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
"""
        try:
            with open(self.virtual_ap_conf, 'w') as f:
                f.write(config_content)
            return True
        except Exception as e:
            logging.error(f"Error creating hostapd config: {e}")
            return False
    
    def setup_dnsmasq_virtual(self):
        """Cấu hình dnsmasq cho virtual interface - sửa lại theo config hiện tại"""
        dnsmasq_conf = f"""interface={self.virtual_iface}
dhcp-range=192.168.4.100,192.168.4.200,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=114.114.114.114
log-dhcp
"""
        try:
            with open("/etc/dnsmasq.d/virtual_ap.conf", 'w') as f:
                f.write(dnsmasq_conf)
            return True
        except Exception as e:
            logging.error(f"Error creating dnsmasq config: {e}")
            return False
    
    def stop_existing_services(self):
        try:
            run_command("systemctl stop hostapd", timeout=5)
            run_command("systemctl stop dnsmasq", timeout=5)
            run_command("pkill hostapd", timeout=5)
            time.sleep(2)
            return True
        except Exception as e:
            logging.error(f"Error stopping services: {e}")
            return False
    
    def start_virtual_ap(self):
        """Khởi động AP trên virtual interface"""
        try:
            if not self.stop_existing_services():
                return False
                
            if not self.create_virtual_interface():
                return False
                
            if not self.create_virtual_hostapd_config():
                return False
                
            if not self.setup_dnsmasq_virtual():
                return False
            
            code, out, err = run_command(f"hostapd -B {self.virtual_ap_conf}", timeout=10)
            if code != 0:
                logging.error(f"Failed to start hostapd: {err}")
                return False
                
            time.sleep(2)
            
            code, out, err = run_command("systemctl start dnsmasq", timeout=10)
            if code != 0:
                logging.error(f"Failed to start dnsmasq: {err}")
                return False
                
            logging.info("Virtual AP started successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error starting virtual AP: {e}")
            return False
    
    def stop_virtual_ap(self):
        """Dừng virtual AP"""
        try:
            run_command("pkill hostapd", timeout=5)
            run_command("systemctl stop dnsmasq", timeout=5)
            run_command(f"iw dev {self.virtual_iface} del", timeout=5)
            run_command("rm -f /etc/dnsmasq.d/virtual_ap.conf", timeout=5)
            return True
        except Exception as e:
            logging.error(f"Error stopping virtual AP: {e}")
            return False

    def restore_original_services(self):
        """Khôi phục services gốc (nếu cần)"""
        try:
            self.stop_virtual_ap()
            run_command("systemctl start hostapd", timeout=10)
            run_command("systemctl start dnsmasq", timeout=10)
            return True
        except Exception as e:
            logging.error(f"Error restoring original services: {e}")
            return False