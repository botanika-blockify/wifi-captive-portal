# /userdata/wifi-captive-portal/backend/virtual_ap_manager.py
import subprocess
import time
import logging
from utils import run_command

class VirtualAPManager:
    def __init__(self, physical_iface="wlan0"):
        self.physical_iface = physical_iface
        self.hostapd_conf = "/etc/hostapd/hostapd.conf"
        
    def setup_concurrent_ap_sta(self):
        """Thiết lập concurrent AP+STA mode"""
        try:
            logging.info("Setting up concurrent AP+STA mode...")
            
            # Dừng services cũ
            run_command("pkill wpa_supplicant 2>/dev/null", timeout=5)
            run_command("systemctl stop hostapd 2>/dev/null", timeout=5)
            time.sleep(2)
            
            # Đảm bảo interface sạch sẽ
            run_command(f"ip addr flush dev {self.physical_iface} 2>/dev/null", timeout=5)
            
            # Khởi động hostapd trước (AP mode)
            logging.info("Starting hostapd for AP mode...")
            code, out, err = run_command("systemctl start hostapd", timeout=10)
            if code != 0:
                logging.error(f"Failed to start hostapd: {err}")
                return False
                
            time.sleep(3)
            
            # Kiểm tra hostapd đang chạy
            code, out, err = run_command("pgrep hostapd")
            if code != 0:
                logging.error("Hostapd not running after start")
                return False
                
            # Khởi động dnsmasq
            logging.info("Starting dnsmasq...")
            code, out, err = run_command("systemctl start dnsmasq", timeout=10)
            if code != 0:
                logging.error(f"Failed to start dnsmasq: {err}")
                return False
                
            # Kiểm tra AP mode đang hoạt động
            code, out, err = run_command(f"iw dev {self.physical_iface} info")
            if code == 0 and "type AP" in out:
                logging.info("AP mode is active")
            else:
                logging.warning("AP mode may not be fully active")
                
            logging.info("Concurrent AP+STA setup completed")
            return True
            
        except Exception as e:
            logging.error(f"Error setting up concurrent AP+STA: {e}")
            return False
    
    def start_client_connection(self, ssid, password):
        """Kết nối client đến WiFi network (STA mode)"""
        try:
            logging.info(f"Starting client connection to: {ssid}")
            
            # Escape SSID và password
            ssid_escaped = ssid.replace("'", "'\\''")
            pwd_escaped = password.replace("'", "'\\''") if password else ""
            
            # Kết nối bằng nmcli - sẽ chạy đồng thời với AP
            if password:
                cmd = f"nmcli dev wifi connect '{ssid_escaped}' password '{pwd_escaped}' ifname {self.physical_iface}"
            else:
                cmd = f"nmcli dev wifi connect '{ssid_escaped}' ifname {self.physical_iface}"
                
            code, out, err = run_command(cmd, timeout=30)
            
            if code == 0:
                logging.info(f"Client connected successfully to {ssid}")
                return True
            else:
                logging.error(f"Client connection failed: {err}")
                return False
                
        except Exception as e:
            logging.error(f"Error in client connection: {e}")
            return False
    
    def check_ap_status(self):
        """Kiểm tra AP mode vẫn hoạt động"""
        try:
            code, out, err = run_command(f"iw dev {self.physical_iface} info")
            if code == 0 and "type AP" in out:
                return True
            return False
        except Exception as e:
            logging.error(f"Error checking AP status: {e}")
            return False
    
    def restore_ap_mode(self):
        """Khôi phục AP mode nếu bị mất"""
        try:
            logging.info("Restoring AP mode...")
            
            # Ngắt kết nối client
            run_command("nmcli con down $(nmcli -t -f NAME con show --active | head -1) 2>/dev/null", timeout=10)
            time.sleep(3)
            
            # Khởi động lại hostapd và dnsmasq
            run_command("systemctl restart hostapd", timeout=10)
            time.sleep(2)
            run_command("systemctl restart dnsmasq", timeout=10)
            
            logging.info("AP mode restored")
            return True
            
        except Exception as e:
            logging.error(f"Error restoring AP mode: {e}")
            return False
    
    def start_virtual_ap(self):
        """Khởi động AP mode"""
        return self.setup_concurrent_ap_sta()
    
    def stop_virtual_ap(self):
        """Dừng AP mode"""
        try:
            run_command("systemctl stop hostapd 2>/dev/null", timeout=5)
            run_command("systemctl stop dnsmasq 2>/dev/null", timeout=5)
            logging.info("AP mode stopped")
            return True
        except Exception as e:
            logging.error(f"Error stopping AP: {e}")
            return False