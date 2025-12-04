import psutil
import platform
import os
import time
from datetime import datetime

class SystemMonitor:
    def __init__(self):
        self.start_time = time.time()
    
    def get_system_info(self):
        """Get comprehensive system information"""
        try:
            # CPU information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            cpu_cores = psutil.cpu_count()
            
            # Memory information
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk information
            disk = psutil.disk_usage('/')
            
            # System information
            boot_time = psutil.boot_time()
            system_uptime = time.time() - boot_time
            
            return {
                "system": {
                    "platform": platform.system(),
                    "platform_version": platform.version(),
                    "architecture": platform.machine(),
                    "hostname": platform.node(),
                    "uptime": self.format_uptime(system_uptime)
                },
                "cpu": {
                    "usage_percent": cpu_percent,
                    "cores": cpu_cores,
                    "frequency_current": cpu_freq.current if cpu_freq else 0,
                    "frequency_max": cpu_freq.max if cpu_freq else 0
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": disk.percent
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"Failed to get system info: {str(e)}"}
    
    def format_uptime(self, seconds):
        """Format uptime to human readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_temperature(self):
        """Get system temperature (requires lm-sensors on Debian)"""
        try:
            # Try to get temperature from different sources
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current:
                            return {
                                "source": name,
                                "temperature": entry.current,
                                "label": entry.label or name
                            }
            
            # Fallback: read from thermal zone (common on Linux)
            thermal_zones = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
                "/sys/class/hwmon/hwmon1/temp1_input"
            ]
            
            for zone in thermal_zones:
                if os.path.exists(zone):
                    with open(zone, 'r') as f:
                        temp = float(f.read().strip()) / 1000.0
                        return {
                            "source": zone.split('/')[-2],
                            "temperature": temp,
                            "label": "CPU Temperature"
                        }
            
            return {"temperature": 25.0, "source": "default", "label": "Estimated"}
            
        except Exception as e:
            return {"temperature": 25.0, "source": "default", "label": "Estimated", "error": str(e)}