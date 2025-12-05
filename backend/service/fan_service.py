import logging
import os

logger = logging.getLogger(__name__)

class FanService:
    def __init__(self):
        self.hwmon_path = "/sys/class/hwmon/hwmon7"
        self.pwm_file = os.path.join(self.hwmon_path, "pwm1")
        self.pwm_enable_file = os.path.join(self.hwmon_path, "pwm1_enable")
        
        self.speed_map = {0: 0, 1: 85, 2: 170, 3: 255}
        
        self._enable_manual_control()
    
    def _enable_manual_control(self):
        try:
            if os.path.exists(self.pwm_enable_file):
                with open(self.pwm_enable_file, 'w') as f:
                    f.write('1')
        except Exception as e:
            logger.warning(f"Could not enable manual control: {e}")
    
    def _read_pwm(self):
        try:
            if os.path.exists(self.pwm_file):
                with open(self.pwm_file, 'r') as f:
                    return int(f.read().strip())
            return 0
        except Exception as e:
            logger.error(f"Error reading PWM: {e}")
            return 0
    
    def _write_pwm(self, value):
        """Write PWM value (0-255)"""
        try:
            if os.path.exists(self.pwm_file):
                with open(self.pwm_file, 'w') as f:
                    f.write(str(value))
                return True
            else:
                logger.error(f"PWM file not found: {self.pwm_file}")
                return False
        except Exception as e:
            logger.error(f"Error writing PWM: {e}")
            return False
    
    def _pwm_to_speed(self, pwm_value):
        if pwm_value == 0:
            return 0
        elif pwm_value <= 85:
            return 1
        elif pwm_value <= 170:
            return 2
        else:
            return 3
    
    def get_status(self):
        try:
            speed_labels = {0: "Off", 1: "Low", 2: "Medium", 3: "High"}
            
            # Read current PWM value
            pwm_value = self._read_pwm()
            speed = self._pwm_to_speed(pwm_value)
            running = pwm_value > 0
            
            return {
                "speed": speed,
                "speed_label": speed_labels.get(speed, "Unknown"),
                "running": running,
                "auto_mode": False,
                "pwm_value": pwm_value
            }
            
        except Exception as e:
            logger.error(f"Error getting fan status: {e}")
            return {
                "speed": 0,
                "speed_label": "Error",
                "running": False,
                "auto_mode": False,
                "error": str(e)
            }
    
    def set_speed(self, speed):
        """Set fan speed (0-3)"""
        try:
            speed = int(speed)
            if 0 <= speed <= 3:
                pwm_value = self.speed_map[speed]
                
                if self._write_pwm(pwm_value):
                    speed_labels = {0: "Off", 1: "Low", 2: "Medium", 3: "High"}
                    return {
                        "success": True,
                        "speed": speed,
                        "running": speed > 0,
                        "pwm_value": pwm_value,
                        "message": f"Fan speed set to {speed_labels[speed]}"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to write to PWM device"
                    }
            else:
                return {
                    "success": False,
                    "error": "Speed must be between 0 and 3"
                }
                
        except ValueError:
            return {
                "success": False,
                "error": "Invalid speed value"
            }
        except Exception as e:
            logger.error(f"Error setting fan speed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def toggle(self):
        """Toggle fan on/off"""
        try:
            current_pwm = self._read_pwm()
            
            if current_pwm > 0:
                # Turn off
                if self._write_pwm(0):
                    return {
                        "success": True,
                        "running": False,
                        "speed": 0,
                        "pwm_value": 0,
                        "message": "Fan stopped"
                    }
            else:
                # Turn on to medium speed
                if self._write_pwm(170):
                    return {
                        "success": True,
                        "running": True,
                        "speed": 2,
                        "pwm_value": 170,
                        "message": "Fan started"
                    }
            
            return {
                "success": False,
                "error": "Failed to toggle fan"
            }
            
        except Exception as e:
            logger.error(f"Error toggling fan: {e}")
            return {
                "success": False,
                "error": str(e)
            }