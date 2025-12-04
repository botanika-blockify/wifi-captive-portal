import logging

logger = logging.getLogger(__name__)

class FanService:
    def __init__(self):
        self.speed = 0  # 0: off, 1: low, 2: medium, 3: high
        self.running = False
        self.auto_mode = True
    
    def get_status(self):
        """Get current fan status"""
        try:
            speed_labels = {0: "Off", 1: "Low", 2: "Medium", 3: "High"}
            
            return {
                "speed": self.speed,
                "speed_label": speed_labels.get(self.speed, "Unknown"),
                "running": self.running,
                "auto_mode": self.auto_mode
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
        """Set fan speed"""
        try:
            speed = int(speed)
            if 0 <= speed <= 3:
                self.speed = speed
                self.running = speed > 0
                
                return {
                    "success": True,
                    "speed": self.speed,
                    "running": self.running,
                    "message": f"Fan speed set to {self.speed}"
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
            self.running = not self.running
            
            if not self.running:
                self.speed = 0
            elif self.speed == 0:
                self.speed = 2  # Default to medium when turning on
            
            return {
                "success": True,
                "running": self.running,
                "speed": self.speed,
                "message": f"Fan {'started' if self.running else 'stopped'}"
            }
            
        except Exception as e:
            logger.error(f"Error toggling fan: {e}")
            return {
                "success": False,
                "error": str(e)
            }