import subprocess
import os

class SystemMonitor:
    def __init__(self):
        pass
    
    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except Exception:
            return ""
    
    def get_system_info(self):
        try:
            cpu_output = self._run_cmd(
                "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'"
            )
            cpu_usage = float(cpu_output) if cpu_output else 0.0
            
            mem_output = self._run_cmd("free -h | awk 'NR==2 {printf \"%s/%s\", $3, $2}'")
            
            disk_output = self._run_cmd(
                "df -h --output=used,size /mnt/data | awk 'NR==2 {printf \"%s/%s\", $1, $2}'"
            )
            temp_output = self._run_cmd("awk '{printf \"%.2f\", $1/1000}' /sys/class/thermal/thermal_zone0/temp")
            temperature = float(temp_output) if temp_output else 0.0
            
            uptime_output = self._run_cmd(
                "awk '{printf \"%dh %dm\", int($1/3600), int(($1%3600)/60)}' /proc/uptime"
            )
            uptime_formatted = uptime_output or "N/A"
            
            return {
                "cpu_usage": cpu_usage,
                "memory": mem_output or "N/A",
                "disk": disk_output or "N/A",
                "temperature": temperature,
                "uptime": uptime_formatted
            }
        except Exception as e:
            return {"error": f"Failed to get system info: {str(e)}"}
