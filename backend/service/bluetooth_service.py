import subprocess
import re
import logging
import time

logger = logging.getLogger(__name__)

class BluetoothService:
    def __init__(self):
        self.is_available = self.check_bluetooth_available()
    
    def check_bluetooth_available(self):
        """Check if Bluetooth is available on the system"""
        try:
            result = subprocess.run(['bluetoothctl', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False
    
    def get_status(self):
        """Get Bluetooth status and connected devices"""
        try:
            if not self.is_available:
                return {
                    "enabled": False,
                    "available": False,
                    "devices": []
                }
            
            power_result = subprocess.run(
                ['bluetoothctl', 'show'], 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=10
            )
            
            powered_match = re.search(r'Powered:\s+(\w+)', power_result.stdout)
            enabled = powered_match.group(1) == 'yes' if powered_match else False
            
            devices_result = subprocess.run(
                ['bluetoothctl', 'devices', 'Paired'], 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=10
            )
            
            devices = []
            for line in devices_result.stdout.split('\n'):
                line = line.strip()
                if line:
                    match = re.match(r'Device\s+([\w:]+)\s+(.+)', line)
                    if match:
                        mac = match.group(1)
                        name = match.group(2)
                        
                        info_result = subprocess.run(
                            ['bluetoothctl', 'info', mac],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        connected = re.search(r'Connected:\s+yes', info_result.stdout) is not None
                        
                        devices.append({
                            "name": name,
                            "mac": mac,
                            "connected": connected
                        })
            
            return {
                "enabled": enabled,
                "available": True,
                "devices": devices
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout getting Bluetooth status")
            return {
                "enabled": False,
                "available": self.is_available,
                "devices": [],
                "error": "Timeout"
            }
        except Exception as e:
            logger.error(f"Error getting Bluetooth status: {e}")
            return {
                "enabled": False,
                "available": self.is_available,
                "devices": [],
                "error": str(e)
            }
    
    def toggle(self):
        """Toggle Bluetooth on/off"""
        try:
            if not self.is_available:
                return {"success": False, "error": "Bluetooth not available"}
            
            status = self.get_status()
            new_state = "off" if status["enabled"] else "on"
            
            result = subprocess.run(
                ['bluetoothctl', 'power', new_state], 
                check=True,
                capture_output=True,
                timeout=10
            )
            
            return {
                "success": True,
                "enabled": not status["enabled"],
                "message": f"Bluetooth turned {new_state}"
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Timeout toggling Bluetooth")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Error toggling Bluetooth: {e}")
            return {"success": False, "error": str(e)}
    
    def scan_devices(self, scan_duration=10):
        """Scan for Bluetooth devices and return discovered devices"""
        try:
            if not self.is_available:
                return {"success": False, "error": "Bluetooth not available"}
            
            # Start scan
            subprocess.run(
                ['bluetoothctl', 'scan', 'on'], 
                check=True,
                capture_output=True,
                timeout=5
            )
            
            # Wait for scan results
            time.sleep(scan_duration)
            
            # Get scan results - sửa lỗi ở đây
            scan_result = subprocess.run(
                ['bluetoothctl', 'devices'], 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=10
            )
            
            # Stop scan
            subprocess.run(
                ['bluetoothctl', 'scan', 'off'], 
                check=True,
                capture_output=True,
                timeout=5
            )
            
            # Parse discovered devices
            devices = []
            for line in scan_result.stdout.split('\n'):
                line = line.strip()
                if line:
                    match = re.match(r'Device\s+([\w:]+)\s+(.+)', line)
                    if match:
                        devices.append({
                            "mac": match.group(1),
                            "name": match.group(2)
                        })
            
            return {
                "success": True,
                "message": f"Scan completed, found {len(devices)} devices",
                "devices": devices
            }
            
        except subprocess.TimeoutExpired:
            subprocess.run(['bluetoothctl', 'scan', 'off'], capture_output=True)
            logger.error("Timeout scanning Bluetooth devices")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Error scanning Bluetooth devices: {e}")
            return {"success": False, "error": str(e)}