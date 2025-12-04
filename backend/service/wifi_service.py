import logging
import subprocess
import shlex
import re

logger = logging.getLogger(__name__)

class WiFiService:
    def __init__(self, client_iface="wlan0", ap_iface="p2p0"):
        self.client_iface = client_iface
        self.ap_iface = ap_iface
    
    def run_command(self, cmd, timeout=30):
        """Execute shell command safely"""
        try:
            p = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = p.communicate(timeout=timeout)
            return p.returncode, out.strip(), err.strip()
        except subprocess.TimeoutExpired:
            if p is not None:
                p.kill()
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def sanitize_ssid(self, ssid):
        """Validate and sanitize SSID"""
        if not ssid or len(ssid) > 32:
            return None
        if not re.match(r'^[a-zA-Z0-9_\-\.\s\u0080-\uFFFF]+$', ssid):
            return None
        return ssid
    
    def sanitize_password(self, password):
        """Validate password"""
        if password and len(password) > 64:
            return None
        return password
    
    def sanitize_connection_name(self, name):
        """Sanitize connection name to prevent command injection"""
        if not re.match(r'^[a-zA-Z0-9 _\-\.]+$', name):
            return None
        return name
    
    def scan_networks(self, timeout=15):
        """Scan for available WiFi networks"""
        try:
            code, out, err = self.run_command(
                f"nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list ifname {self.client_iface}",
                timeout=timeout
            )
            
            networks = []
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3:
                        security = parts[-1]
                        signal = parts[-2]
                        ssid = ":".join(parts[:-2])
                        if ssid and ssid != "--":
                            networks.append({
                                "ssid": ssid,
                                "signal": int(signal) if signal.isdigit() else None,
                                "security": security
                            })
            
            networks.sort(key=lambda x: x["signal"] or 0, reverse=True)
            return {"success": True, "networks": networks}
        
        except Exception as e:
            logger.error(f"Error scanning networks: {e}")
            return {"success": False, "error": str(e)}
    
    def connect_network(self, ssid, password="", timeout=40):
        """Connect to WiFi network"""
        try:
            # Validate inputs
            if not self.sanitize_ssid(ssid):
                return {"success": False, "error": "Invalid SSID"}
            
            if not self.sanitize_password(password):
                return {"success": False, "error": "Invalid password"}
            
            # Set interface management
            self.run_command(f"nmcli device set {self.client_iface} managed yes", timeout=5)
            self.run_command(f"nmcli device set {self.ap_iface} managed no", timeout=5)
            
            # Build connection command
            ssid_escaped = shlex.quote(ssid)
            
            if password:
                pwd_escaped = shlex.quote(password)
                cmd = f"nmcli --wait 40 dev wifi connect {ssid_escaped} password {pwd_escaped} ifname {self.client_iface}"
            else:
                cmd = f"nmcli --wait 40 dev wifi connect {ssid_escaped} ifname {self.client_iface}"
            
            code, out, err = self.run_command(cmd, timeout=timeout)
            
            if code == 0:
                return {"success": True, "message": "Connected successfully"}
            else:
                return {"success": False, "error": "Connection failed. Please try again"}
        
        except Exception as e:
            logger.error(f"Error connecting to network: {e}")
            return {"success": False, "error": str(e)}
    
    def get_current_connection(self):
        """Get currently connected WiFi network"""
        try:
            # Check active connection on client interface
            code, out, _ = self.run_command("nmcli -t -f NAME,TYPE,DEVICE connection show --active")
            
            current_ssid = None
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3 and parts[2] == self.client_iface:
                        conn_name = parts[0]
                        safe_conn_name = self.sanitize_connection_name(conn_name)
                        if not safe_conn_name:
                            continue
                        
                        # Get SSID from connection
                        code2, out2, _ = self.run_command(
                            f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}"
                        )
                        if code2 == 0 and out2:
                            ssid_line = out2.split(":", 1)
                            if len(ssid_line) > 1:
                                current_ssid = ssid_line[1].strip()
                        break
            
            # Fallback: check iwconfig
            if not current_ssid:
                code, out, _ = self.run_command(f"iwconfig {self.client_iface}")
                if code == 0 and 'ESSID:"' in out:
                    match = re.search(r'ESSID:"([^"]+)"', out)
                    if match:
                        current_ssid = match.group(1)
            
            if current_ssid and current_ssid != "off/any":
                # Get signal strength
                signal = self._get_signal_strength(current_ssid)
                
                return {
                    "success": True,
                    "connected": True,
                    "ssid": current_ssid,
                    "signal": signal,
                    "interface": self.client_iface
                }
            else:
                return {"success": True, "connected": False}
        
        except Exception as e:
            logger.error(f"Error getting current connection: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_signal_strength(self, ssid):
        """Get signal strength for specific SSID"""
        try:
            code, out, _ = self.run_command(f"nmcli -t -f SSID,SIGNAL dev wifi list ifname {self.client_iface}")
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        scan_ssid = ":".join(parts[:-1])
                        sig = parts[-1]
                        if scan_ssid == ssid and sig.isdigit():
                            return int(sig)
            return None
        except:
            return None
    
    def get_saved_networks(self):
        """Get list of saved WiFi networks"""
        try:
            code, out, _ = self.run_command("nmcli -t -f NAME,TYPE connection show")
            
            saved_networks = []
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2 and "wifi" in parts[1].lower():
                        conn_name = parts[0]
                        safe_conn_name = self.sanitize_connection_name(conn_name)
                        if not safe_conn_name:
                            continue
                        
                        # Get SSID from connection
                        code2, out2, _ = self.run_command(
                            f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}"
                        )
                        if code2 == 0 and out2:
                            ssid_line = out2.split(":", 1)
                            if len(ssid_line) > 1:
                                ssid = ssid_line[1].strip()
                                if ssid and ssid not in [n["ssid"] for n in saved_networks]:
                                    saved_networks.append({
                                        "ssid": ssid,
                                        "connection_name": conn_name
                                    })
            
            return {"success": True, "networks": saved_networks}
        
        except Exception as e:
            logger.error(f"Error getting saved networks: {e}")
            return {"success": False, "error": str(e)}
    
    def forget_network(self, ssid):
        """Delete a saved WiFi connection"""
        try:
            if not ssid:
                return {"success": False, "error": "SSID required"}
            
            # Find connection by SSID
            code, out, _ = self.run_command("nmcli -t -f NAME,TYPE connection show")
            
            deleted = False
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2 and "wifi" in parts[1].lower():
                        conn_name = parts[0]
                        safe_conn_name = self.sanitize_connection_name(conn_name)
                        if not safe_conn_name:
                            continue
                        
                        # Check if this connection matches the SSID
                        code2, out2, _ = self.run_command(
                            f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}"
                        )
                        if code2 == 0 and out2:
                            ssid_line = out2.split(":", 1)
                            if len(ssid_line) > 1 and ssid_line[1].strip() == ssid:
                                # Delete this connection
                                code3, _, _ = self.run_command(
                                    f"nmcli connection delete {shlex.quote(safe_conn_name)}"
                                )
                                if code3 == 0:
                                    deleted = True
                                    break
            
            if deleted:
                return {"success": True, "message": f"Forgot network: {ssid}"}
            else:
                return {"success": False, "error": "Network not found"}
        
        except Exception as e:
            logger.error(f"Error forgetting network: {e}")
            return {"success": False, "error": str(e)}
    
    def disconnect_current(self):
        """Disconnect and forget current WiFi connection"""
        try:
            # Get current connection
            code, out, _ = self.run_command("nmcli -t -f NAME,TYPE,DEVICE connection show --active")
            
            current_conn_name = None
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3 and parts[2] == self.client_iface:
                        conn_name = parts[0]
                        safe_conn_name = self.sanitize_connection_name(conn_name)
                        if safe_conn_name:
                            current_conn_name = safe_conn_name
                            break
            
            if not current_conn_name:
                return {"success": False, "error": "No active connection"}
            
            # Disconnect and delete
            code, _, _ = self.run_command(f"nmcli connection delete {shlex.quote(current_conn_name)}")
            
            if code == 0:
                return {"success": True, "message": "Disconnected and forgot current network"}
            else:
                return {"success": False, "error": "Failed to disconnect"}
        
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return {"success": False, "error": str(e)}
