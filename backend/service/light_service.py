import logging
import subprocess
import os

logger = logging.getLogger(__name__)

class LightService:
    def __init__(self):
        self.lights = {
            'main': {
                'name': 'Main Light',
                'pin': 17,  # GPIO pin for main light
                'state': False,
                'brightness': 100,
                'color': 'white'
            },
            'secondary': {
                'name': 'Secondary Light', 
                'pin': 18,  # GPIO pin for secondary light
                'state': False,
                'brightness': 100,
                'color': 'white'
            }
        }
        self.gpio_available = self.check_gpio_availability()
        self.setup_gpio()
    
    def check_gpio_availability(self):
        """Check if GPIO is available on the system"""
        try:
            import RPi.GPIO as GPIO
            return True
        except (ImportError, RuntimeError):
            logger.warning("RPi.GPIO not available, using simulated GPIO")
            return False
    
    def setup_gpio(self):
        """Setup GPIO pins for light control"""
        if self.gpio_available:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                for light_id, light_config in self.lights.items():
                    GPIO.setup(light_config['pin'], GPIO.OUT)
                    GPIO.output(light_config['pin'], GPIO.LOW)
                logger.info("GPIO setup completed successfully")
            except Exception as e:
                logger.error(f"GPIO setup failed: {e}")
                self.gpio_available = False
        else:
            logger.info("Using simulated GPIO for light control")
    
    def get_status(self):
        """Get status of all lights"""
        try:
            lights_status = []
            for light_id, light_config in self.lights.items():
                lights_status.append({
                    'id': light_id,
                    'name': light_config['name'],
                    'state': light_config['state'],
                    'brightness': light_config['brightness'],
                    'color': light_config['color'],
                    'gpio_available': self.gpio_available
                })
            
            return {
                "lights": lights_status,
                "gpio_available": self.gpio_available,
                "total_lights": len(lights_status)
            }
            
        except Exception as e:
            logger.error(f"Error getting lights status: {e}")
            return {
                "lights": [],
                "gpio_available": False,
                "error": str(e)
            }
    
    def toggle_light(self, light_id):
        """Toggle light on/off"""
        try:
            if light_id not in self.lights:
                return {"success": False, "error": f"Light {light_id} not found"}
            
            light = self.lights[light_id]
            new_state = not light['state']
            
            # Control actual GPIO if available
            if self.gpio_available:
                import RPi.GPIO as GPIO
                GPIO.output(light['pin'], GPIO.HIGH if new_state else GPIO.LOW)
            
            light['state'] = new_state
            
            return {
                "success": True,
                "light_id": light_id,
                "state": new_state,
                "message": f"Light turned {'on' if new_state else 'off'}"
            }
            
        except Exception as e:
            logger.error(f"Error toggling light {light_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def set_brightness(self, light_id, brightness):
        """Set light brightness (0-100)"""
        try:
            if light_id not in self.lights:
                return {"success": False, "error": f"Light {light_id} not found"}
            
            brightness = int(brightness)
            if not 0 <= brightness <= 100:
                return {"success": False, "error": "Brightness must be between 0 and 100"}
            
            light = self.lights[light_id]
            light['brightness'] = brightness
            
            # For real hardware, you would use PWM here
            if self.gpio_available and brightness > 0:
                light['state'] = True
            
            return {
                "success": True,
                "light_id": light_id,
                "brightness": brightness,
                "message": f"Brightness set to {brightness}%"
            }
            
        except ValueError:
            return {"success": False, "error": "Invalid brightness value"}
        except Exception as e:
            logger.error(f"Error setting brightness for {light_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def set_color(self, light_id, color):
        """Set light color (for RGB lights)"""
        try:
            if light_id not in self.lights:
                return {"success": False, "error": f"Light {light_id} not found"}
            
            valid_colors = ['white', 'warm', 'cool', 'red', 'green', 'blue', 'yellow', 'purple']
            if color not in valid_colors:
                return {"success": False, "error": f"Invalid color. Must be one of: {valid_colors}"}
            
            light = self.lights[light_id]
            light['color'] = color
            
            # For real RGB LED control, you would set GPIO pins for each color channel
            logger.info(f"Setting light {light_id} color to {color}")
            
            return {
                "success": True,
                "light_id": light_id,
                "color": color,
                "message": f"Color set to {color}"
            }
            
        except Exception as e:
            logger.error(f"Error setting color for {light_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        if self.gpio_available:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
                logger.info("GPIO cleanup completed")
            except Exception as e:
                logger.error(f"GPIO cleanup failed: {e}")