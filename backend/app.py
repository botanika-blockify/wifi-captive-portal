import os
import time
import subprocess
import shlex
import string
from flask import Flask, request, jsonify, send_from_directory, redirect, Response
from service import FanService, WiFiService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
AP_IFACE = "p2p0"     
CLIENT_IFACE = "wlan0"   

app = Flask(__name__, static_folder=None)

# Initialize services
fan_service = FanService()
wifi_service = WiFiService(client_iface=CLIENT_IFACE, ap_iface=AP_IFACE)

class Config:
    MAX_CONNECTION_ATTEMPTS = 3
    CONNECTION_TIMEOUT = 45
    SCAN_TIMEOUT = 15

# Helper function for AP password management (keep only what's needed)
def run_command(cmd: str, timeout=30):
    """Execute shell command - used only for system operations"""
    p = None
    try:
        p = subprocess.Popen(shlex.split(cmd), 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           text=True)
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out.strip(), err.strip()
    except subprocess.TimeoutExpired:
        if p:
            p.kill()
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def sanitize_ap_password(password):
    """Sanitize and validate password for hostapd.conf"""
    if not password:
        return None
    
    # Check length (WPA2 standard: 8-63 characters)
    if len(password) < 8 or len(password) > 63:
        return None
    
    # Only allow ASCII printable characters
    allowed_chars = string.ascii_letters + string.digits + string.punctuation
    
    # Block dangerous characters
    dangerous_chars = ['`', '$', '\\', '\n', '\r', '\0']
    
    for char in password:
        if char not in allowed_chars or char in dangerous_chars:
            return None
    
    return password

@app.get("/api/scan")
def api_scan():
    try:
        result = wifi_service.scan_networks(timeout=Config.SCAN_TIMEOUT)
        
        if not result["success"]:
            return jsonify({"ok": False, "error": "Scan failed"}), 500
        
        networks = result.get("networks", [])
        
        conn_result = wifi_service.get_current_connection()
        current_ssid = None
        
        if conn_result.get("success") and conn_result.get("connected"):
            ssid_value = conn_result.get("ssid")
            current_ssid = ssid_value.strip() if isinstance(ssid_value, str) else None
        
        if current_ssid:
            networks = [net for net in networks if net.get("ssid", "").strip() != current_ssid]
        
        return jsonify({"ok": True, "networks": networks})
        
    except Exception as e:
        print(f"Error in api_scan: {e}")
        return jsonify({"ok": False, "error": "Scan failed"}), 500

@app.post("/api/connect")
def api_connect():
    """Connect to WiFi network"""
    try:
        data = request.get_json(silent=True) or {}
        ssid = (data.get("ssid") or "").strip()
        pwd = (data.get("password") or "").strip()

        if not ssid:
            return jsonify({"ok": False, "error": "SSID required"}), 400

        result = wifi_service.connect_network(ssid, pwd, timeout=40)
        
        if result["success"]:
            return jsonify({"ok": True, "message": result["message"]}), 200
        else:
            return jsonify({"ok": False, "error": result["error"]}), 400
    except Exception as e:
        print(f"Error in api_connect: {e}")
        return jsonify({"ok": False, "error": "Connection failed"}), 500

@app.get("/api/status")
def api_status():
    """Get system status"""
    try:
        code_ip, out_ip, _ = run_command(f"ip -br addr show dev {CLIENT_IFACE}")
        code_rt, out_rt, _ = run_command("ip route show default")
        code_ping, _, _ = run_command("ping -c1 -w2 8.8.8.8")
        code_conn, out_conn, _ = run_command("nmcli -t connection show --active")
        
        code_wifi, out_wifi, _ = run_command(f"iwconfig {CLIENT_IFACE}")
        
        code_ap, _, _ = run_command("sudo systemctl is-active hostapd")
        ap_active = (code_ap == 0)
        
        # Get client connection status from WiFi service
        conn_result = wifi_service.get_current_connection()
        client_connected = conn_result.get("success") and conn_result.get("connected", False)
        
        return jsonify({
            "ok": True, 
            "client_iface": CLIENT_IFACE,
            "ap_iface": AP_IFACE,
            "ap_mode": ap_active,
            "client_connected": client_connected,
            "ip": out_ip,
            "default_route": out_rt,
            "internet": code_ping == 0,
            "active_connections": out_conn,
            "wifi_connection": out_wifi
        })
    
    except Exception as e:
        return jsonify({"ok": False, "error": "Status check failed"}), 500

@app.get("/api/health")
def api_health():
    """Health check endpoint"""
    # Get client connection status from WiFi service
    conn_result = wifi_service.get_current_connection()
    client_connected = conn_result.get("success") and conn_result.get("connected", False)
    
    code_ap, _, _ = run_command("sudo systemctl is-active hostapd")
    ap_active = (code_ap == 0)
    
    return jsonify({
        "status": "healthy",
        "service": "wifi-portal",
        "timestamp": time.time(),
        "version": "1.0.0",
        "ap_mode": ap_active,
        "ap_interface": AP_IFACE,
        "client_interface": CLIENT_IFACE,
        "client_connected": client_connected
    })

@app.get("/generate_204")
def generate_204():
    return redirect("/", code=302)

@app.get("/gen_204")
def gen_204():
    return redirect("/", code=302)

@app.get("/library/test/success.html")
def library_test_success():
    return redirect("/", code=302)

@app.get("/hotspot-detect.html")
def hotspot_detect_html():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0;url=/">
        <title>Network Authentication Required</title>
    </head>
    <body>
        <p>Redirecting to authentication page...</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.get("/hotspot-detect")
def hotspot_detect():
    return redirect("/", code=302)

@app.get("/ncsi.txt")
def ncsi_txt():
    return redirect("/", code=302)

@app.get("/connecttest.txt")
def connecttest_txt():
    return redirect("/", code=302)

@app.get("/redirect")
def redirect_captive():
    return redirect("/", code=302)

@app.get("/captiveportal")
def captiveportal():
    return redirect("/", code=302)

@app.get("/fs/captiveportal")
def fs_captiveportal():
    return redirect("/", code=302)

@app.get("/success.txt")
def success_txt():
    return redirect("/", code=302)

@app.get("/api/current-connection")
def api_current_connection():
    """Get currently connected WiFi network on client interface"""
    try:
        result = wifi_service.get_current_connection()
        
        if result["success"]:
            if result.get("connected"):
                return jsonify({
                    "ok": True,
                    "connected": True,
                    "ssid": result["ssid"],
                    "signal": result.get("signal"),
                    "interface": result["interface"]
                })
            else:
                return jsonify({"ok": True, "connected": False})
        else:
            return jsonify({"ok": False, "error": "Failed to get connection status"}), 500
    except Exception as e:
        print(f"Error in api_current_connection: {e}")
        return jsonify({"ok": False, "error": "Failed to get connection status"}), 500

@app.get("/api/saved-networks")
def api_saved_networks():
    """Get list of saved WiFi networks"""
    try:
        result = wifi_service.get_saved_networks()
        
        if result["success"]:
            return jsonify({"ok": True, "networks": result["networks"]})
        else:
            return jsonify({"ok": False, "error": "Failed to load saved networks"}), 500
    except Exception as e:
        print(f"Error in api_saved_networks: {e}")
        return jsonify({"ok": False, "error": "Failed to load saved networks"}), 500

@app.post("/api/forget-network")
def api_forget_network():
    """Delete a saved WiFi connection"""
    try:
        data = request.get_json(silent=True) or {}
        ssid = (data.get("ssid") or "").strip()
        
        if not ssid:
            return jsonify({"ok": False, "error": "SSID required"}), 400
        
        result = wifi_service.forget_network(ssid)
        
        if result["success"]:
            return jsonify({"ok": True, "message": result["message"]})
        else:
            return jsonify({"ok": False, "error": result["error"]}), 404
    except Exception as e:
        print(f"Error in api_forget_network: {e}")
        return jsonify({"ok": False, "error": "Failed to forget network"}), 500

@app.post("/api/disconnect-current")
def api_disconnect_current():
    """Disconnect and forget current WiFi connection"""
    try:
        result = wifi_service.disconnect_current()
        
        if result["success"]:
            return jsonify({"ok": True, "message": result["message"]})
        else:
            error_msg = result.get("error", "")
            error_code = 404 if isinstance(error_msg, str) and "No active" in error_msg else 500
            return jsonify({"ok": False, "error": error_msg}), error_code
    except Exception as e:
        print(f"Error in api_disconnect_current: {e}")
        return jsonify({"ok": False, "error": "Failed to disconnect"}), 500

@app.post("/api/change-ap-password")
def api_change_ap_password():
    """Change AP password in hostapd configuration"""
    data = request.get_json(silent=True) or {}
    new_password = (data.get("password") or "").strip()
    
    # Sanitize and validate password
    sanitized_password = sanitize_ap_password(new_password)
    
    if not sanitized_password:
        if not new_password:
            return jsonify({"ok": False, "error": "Password required"}), 400
        elif len(new_password) < 8:
            return jsonify({"ok": False, "error": "Password must be at least 8 characters"}), 400
        elif len(new_password) > 63:
            return jsonify({"ok": False, "error": "Password must not exceed 63 characters"}), 400
        else:
            return jsonify({"ok": False, "error": "Password contains invalid characters"}), 400
    
    try:
        hostapd_conf = "/etc/hostapd/hostapd.conf"
        
        # Read current config
        with open(hostapd_conf, 'r') as f:
            lines = f.readlines()
        
        # Update wpa_passphrase line with sanitized password
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('wpa_passphrase='):
                # Safely write password without any shell interpretation
                new_lines.append(f'wpa_passphrase={sanitized_password}\n')
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            return jsonify({"ok": False, "error": "Configuration error"}), 500
        
        # Write updated config atomically
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir='/etc/hostapd') as tmp_file:
            tmp_file.writelines(new_lines)
            tmp_path = tmp_file.name
        
        # Atomic move
        import shutil
        shutil.move(tmp_path, hostapd_conf)
        
        # Set proper permissions
        os.chmod(hostapd_conf, 0o600)
        
        # Restart hostapd to apply changes
        run_command("sudo systemctl restart hostapd", timeout=10)
        time.sleep(2)
        
        return jsonify({"ok": True, "message": "AP password updated successfully"})
    
    except PermissionError:
        print("Permission denied: Cannot modify hostapd.conf")
        return jsonify({"ok": False, "error": "Permission denied"}), 500
    except Exception as e:
        print(f"Error in api_change_ap_password: {e}")
        return jsonify({"ok": False, "error": "Failed to update AP password"}), 500

@app.get("/api/ap-info")
def api_ap_info():
    """Get current AP information (SSID only, not password)"""
    try:
        hostapd_conf = "/etc/hostapd/hostapd.conf"
        
        ssid = None
        with open(hostapd_conf, 'r') as f:
            for line in f:
                if line.strip().startswith('ssid='):
                    ssid = line.split('=', 1)[1].strip()
                    break
        
        return jsonify({
            "ok": True,
            "ssid": ssid or "Unknown",
            "interface": AP_IFACE
        })
    
    except Exception as e:
        print(f"Error in api_ap_info: {e}")
        return jsonify({"ok": False, "error": "Failed to get AP info"}), 500

# Fan Control APIs
@app.get("/api/fan/status")
def api_fan_status():
    """Get current fan status"""
    try:
        status = fan_service.get_status()
        return jsonify({"ok": True, "fan": status})
    except Exception as e:
        print(f"Error in api_fan_status: {e}")
        return jsonify({"ok": False, "error": "Failed to get fan status"}), 500

@app.post("/api/fan/speed")
def api_fan_set_speed():
    """Set fan speed (0-3)"""
    try:
        data = request.get_json(silent=True) or {}
        speed = data.get("speed")
        
        if speed is None:
            return jsonify({"ok": False, "error": "Speed required"}), 400
        
        result = fan_service.set_speed(speed)
        
        if result.get("success"):
            return jsonify({"ok": True, "fan": result})
        else:
            return jsonify({"ok": False, "error": result.get("error")}), 400
    
    except Exception as e:
        print(f"Error in api_fan_set_speed: {e}")
        return jsonify({"ok": False, "error": "Failed to set fan speed"}), 500

@app.post("/api/fan/toggle")
def api_fan_toggle():
    """Toggle fan on/off"""
    try:
        result = fan_service.toggle()
        
        if result.get("success"):
            return jsonify({"ok": True, "fan": result})
        else:
            return jsonify({"ok": False, "error": result.get("error")}), 400
    
    except Exception as e:
        print(f"Error in api_fan_toggle: {e}")
        return jsonify({"ok": False, "error": "Failed to toggle fan"}), 500

@app.get("/canonical.html")
def canonical_html():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0;url=/">
        <title>Redirecting</title>
    </head>
    <body>
        <p>Redirecting to authentication page...</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.get("/")
def serve_index():
    return Response(
        open(os.path.join(FRONTEND_DIR, "index.html")).read(),
        mimetype="text/html"
    )
@app.route("/success.html")
def serve_success():
    return send_from_directory(FRONTEND_DIR, "success.html")

@app.route("/public/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "public"), filename)

@app.route("/<path:path>")
def serve_frontend(path):
    # Prevent path traversal attacks
    if ".." in path or path.startswith("/"):
        return send_from_directory(FRONTEND_DIR, "index.html")
    
    full_path = os.path.join(FRONTEND_DIR, path)
    # Ensure the resolved path is within FRONTEND_DIR
    if not os.path.abspath(full_path).startswith(os.path.abspath(FRONTEND_DIR)):
        return send_from_directory(FRONTEND_DIR, "index.html")
    
    if os.path.exists(full_path):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)
