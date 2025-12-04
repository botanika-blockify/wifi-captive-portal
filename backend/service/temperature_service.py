import subprocess
import re
import logging
from system_monitor import SystemMonitor

logger = logging.getLogger(__name__)

class TemperatureService:
    def __init__(self):
        self.system_monitor = SystemMonitor()
        self.target_temperature = 23.0
    
    def get_status(self):
        """Get actual system temperature"""
        try:
            # Get real system temperature
            system_temp = self.system_monitor.get_temperature()
            current_temp = system_temp.get('temperature', 25.0)
            
            return {
                "current_temp": round(current_temp, 1),
                "target_temp": self.target_temperature,
                "source": system_temp.get('source', 'sensor'),
                "label": system_temp.get('label', 'System Temperature'),
                "unit": "°C",
                "timestamp": self.get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error getting temperature: {e}")
            return {
                "current_temp": 25.0,
                "target_temp": self.target_temperature,
                "source": "default",
                "label": "System Temperature", 
                "unit": "°C",
                "error": str(e)
            }
    
    def set_temperature(self, temperature):
        """Set target temperature (for climate control simulation)"""
        try:
            temp = float(temperature)
            if 16.0 <= temp <= 35.0:
                self.target_temperature = temp
                return {
                    "success": True,
                    "target_temp": self.target_temperature,
                    "message": f"Target temperature set to {temp}°C"
                }
            else:
                return {
                    "success": False,
                    "error": "Temperature must be between 16°C and 35°C"
                }
                
        except ValueError:
            return {
                "success": False,
                "error": "Invalid temperature value"
            }
        except Exception as e:
            logger.error(f"Error setting temperature: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_timestamp(self):
        from datetime import datetime
        return datetime.now().isoformat()