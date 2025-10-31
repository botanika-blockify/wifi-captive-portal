# /userdata/wifi-captive-portal/backend/utils.py
import subprocess
import shlex

def run_command(cmd: str, timeout=30):
    try:
        p = subprocess.Popen(shlex.split(cmd), 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           text=True)
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out.strip(), err.strip()
    except subprocess.TimeoutExpired:
        p.kill()
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def validate_ssid(ssid):
    if not ssid or len(ssid) > 32:
        return False
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', ssid):
        return False
    return True

def validate_password(password):
    if password and len(password) > 64:
        return False
    return True