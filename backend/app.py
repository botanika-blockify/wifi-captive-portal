import os, subprocess, shlex
import time
import re
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
AP_IFACE = "p2p0"     
CLIENT_IFACE = "wlan0"   
WIFI_IFACE = CLIENT_IFACE  

app = Flask(__name__, static_folder=None)

class Config:
    MAX_CONNECTION_ATTEMPTS = 3
    CONNECTION_TIMEOUT = 45
    SCAN_TIMEOUT = 15

def run(cmd: str, timeout=30):
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

def sanitize_password(password):
    """Sanitize and validate password for hostapd.conf"""
    # Remove any special shell characters that could cause injection
    # WPA2 passwords can only contain ASCII printable characters
    if not password:
        return None
    
    # Check length (WPA2 standard: 8-63 characters)
    if len(password) < 8 or len(password) > 63:
        return None
    
    # Only allow ASCII printable characters (no shell special chars)
    import string
    allowed_chars = string.ascii_letters + string.digits + string.punctuation
    
    # Remove any characters that could cause issues in config file
    # Specifically block: backticks, $, quotes that could break config
    dangerous_chars = ['`', '$', '\\', '\n', '\r', '\0']
    
    for char in password:
        if char not in allowed_chars or char in dangerous_chars:
            return None
    
    return password

def sanitize_connection_name(name):
    """Sanitize connection name to prevent command injection"""
    # Only allow alphanumeric, spaces, hyphens, underscores, dots
    if not re.match(r'^[a-zA-Z0-9 _\-\.]+$', name):
        return None
    return name

def is_client_connected():
    try:
        code, out, _ = run(f"nmcli -t dev status | grep {CLIENT_IFACE}")
        if code == 0 and "connected" in out:
            return True
        
        code, out, _ = run(f"iwconfig {CLIENT_IFACE}")
        if code == 0 and "ESSID" in out and "off/any" not in out:
            return True
            
        return False
    except:
        return False

def validate_ssid(ssid):
    if not ssid or len(ssid) > 32:
        return False
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.\s\u0080-\uFFFF]+$', ssid):
        return False
    return True

def validate_password(password):
    if password and len(password) > 64:
        return False
    return True

def get_wifi_security_type(ssid):
    try:
        code, out, err = run("nmcli -t -f SSID,SECURITY dev wifi list", timeout=10)
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2:
                    current_ssid = ":".join(parts[:-1])
                    security = parts[-1]
                    if current_ssid == ssid:
                        return security
        return "unknown"
    except Exception as e:
        return "unknown"

@app.get("/api/scan")
def api_scan():
    try:
        code, out, err = run(f"nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list ifname {CLIENT_IFACE}", 
                           timeout=Config.SCAN_TIMEOUT)
        
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
        
        return jsonify({"ok": True, "networks": networks})
    
    except Exception as e:
        return jsonify({"ok": False, "error": "Scan failed"}), 500

@app.post("/api/connect")
def api_connect():
    data = request.get_json(silent=True) or {}
    ssid = (data.get("ssid") or "").strip()
    pwd = (data.get("password") or "").strip()

    if not ssid:
        return jsonify({"ok": False, "error": "SSID required"}), 400

    if not validate_ssid(ssid):
        return jsonify({"ok": False, "error": "Invalid SSID"}), 400
    
    if not validate_password(pwd):
        return jsonify({"ok": False, "error": "Invalid password"}), 400

    run(f"nmcli device set {CLIENT_IFACE} managed yes", timeout=5)
    run(f"nmcli device set {AP_IFACE} managed no", timeout=5)

    ssid_escaped = shlex.quote(ssid)
    pwd_escaped = shlex.quote(pwd) if pwd else ""

    if pwd:
        cmd = f"nmcli --wait 40 dev wifi connect {ssid_escaped} password {pwd_escaped} ifname {CLIENT_IFACE}"
    else:
        cmd = f"nmcli --wait 40 dev wifi connect {ssid_escaped} ifname {CLIENT_IFACE}"

    code, out, err = run(cmd, timeout=40)

    if code == 0:
        return jsonify({"ok": True, "message": "Connected"}), 200

    return jsonify({
        "ok": False,
        "error": "Connection failed. Please try again"
    }), 400

@app.get("/api/status")
def api_status():
    try:
        code_ip, out_ip, _ = run(f"ip -br addr show dev {CLIENT_IFACE}")
        code_rt, out_rt, _ = run("ip route show default")
        code_ping, _, _ = run("ping -c1 -w2 8.8.8.8")
        code_conn, out_conn, _ = run("nmcli -t connection show --active")
        
        code_wifi, out_wifi, _ = run(f"iwconfig {CLIENT_IFACE}")
        
        code_ap, _, _ = run("sudo systemctl is-active hostapd")
        ap_active = (code_ap == 0)
        
        client_connected = is_client_connected()
        
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
    client_connected = is_client_connected()
    code_ap, _, _ = run("sudo systemctl is-active hostapd")
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
        # Check active connection on client interface
        code, out, _ = run(f"nmcli -t -f NAME,TYPE,DEVICE connection show --active")
        
        current_ssid = None
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 3 and parts[2] == CLIENT_IFACE:
                    conn_name = parts[0]
                    # Sanitize connection name to prevent injection
                    safe_conn_name = sanitize_connection_name(conn_name)
                    if not safe_conn_name:
                        continue
                    # Get SSID from connection
                    code2, out2, _ = run(f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}")
                    if code2 == 0 and out2:
                        ssid_line = out2.split(":", 1)
                        if len(ssid_line) > 1:
                            current_ssid = ssid_line[1].strip()
                    break
        
        # Fallback: check iwconfig
        if not current_ssid:
            code, out, _ = run(f"iwconfig {CLIENT_IFACE}")
            if code == 0 and 'ESSID:"' in out:
                import re
                match = re.search(r'ESSID:"([^"]+)"', out)
                if match:
                    current_ssid = match.group(1)
        
        if current_ssid and current_ssid != "off/any":
            # Get signal strength for the connected SSID
            code, out, _ = run(f"nmcli -t -f SSID,SIGNAL dev wifi list ifname {CLIENT_IFACE}")
            signal = None
            if code == 0 and out:
                for line in out.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        ssid = ":".join(parts[:-1])  # Handle SSIDs with colons
                        sig = parts[-1]
                        if ssid == current_ssid and sig.isdigit():
                            signal = int(sig)
                            break
            
            return jsonify({
                "ok": True,
                "connected": True,
                "ssid": current_ssid,
                "signal": signal,
                "interface": CLIENT_IFACE
            })
        else:
            return jsonify({"ok": True, "connected": False})
    
    except Exception as e:
        print(f"Error in api_current_connection: {e}")  # Log to server only
        return jsonify({"ok": False, "error": "Failed to get connection status"}), 500

@app.get("/api/saved-networks")
def api_saved_networks():
    """Get list of saved WiFi networks"""
    try:
        code, out, _ = run("nmcli -t -f NAME,TYPE connection show")
        
        saved_networks = []
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and "wifi" in parts[1].lower():
                    conn_name = parts[0]
                    # Sanitize connection name
                    safe_conn_name = sanitize_connection_name(conn_name)
                    if not safe_conn_name:
                        continue
                    # Get SSID from connection
                    code2, out2, _ = run(f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}")
                    if code2 == 0 and out2:
                        ssid_line = out2.split(":", 1)
                        if len(ssid_line) > 1:
                            ssid = ssid_line[1].strip()
                            if ssid and ssid not in [n["ssid"] for n in saved_networks]:
                                saved_networks.append({
                                    "ssid": ssid,
                                    "connection_name": conn_name
                                })
        
        return jsonify({"ok": True, "networks": saved_networks})
    
    except Exception as e:
        print(f"Error in api_saved_networks: {e}")  # Log to server only
        return jsonify({"ok": False, "error": "Failed to load saved networks"}), 500

@app.post("/api/forget-network")
def api_forget_network():
    """Delete a saved WiFi connection"""
    data = request.get_json(silent=True) or {}
    ssid = (data.get("ssid") or "").strip()
    
    if not ssid:
        return jsonify({"ok": False, "error": "SSID required"}), 400
    
    try:
        # Find connection by SSID
        code, out, _ = run("nmcli -t -f NAME,TYPE connection show")
        
        deleted = False
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and "wifi" in parts[1].lower():
                    conn_name = parts[0]
                    # Sanitize connection name
                    safe_conn_name = sanitize_connection_name(conn_name)
                    if not safe_conn_name:
                        continue
                    # Check if this connection matches the SSID
                    code2, out2, _ = run(f"nmcli -t -f 802-11-wireless.ssid connection show {shlex.quote(safe_conn_name)}")
                    if code2 == 0 and out2:
                        ssid_line = out2.split(":", 1)
                        if len(ssid_line) > 1 and ssid_line[1].strip() == ssid:
                            # Delete this connection
                            code3, _, _ = run(f"nmcli connection delete {shlex.quote(safe_conn_name)}")
                            if code3 == 0:
                                deleted = True
                                break
        
        if deleted:
            return jsonify({"ok": True, "message": f"Forgot network: {ssid}"})
        else:
            return jsonify({"ok": False, "error": "Network not found"}), 404
    
    except Exception as e:
        print(f"Error in api_forget_network: {e}")  # Log to server only
        return jsonify({"ok": False, "error": "Failed to forget network"}), 500

@app.post("/api/disconnect-current")
def api_disconnect_current():
    """Disconnect and forget current WiFi connection"""
    try:
        # Get current connection on client interface
        code, out, _ = run(f"nmcli -t -f NAME,TYPE,DEVICE connection show --active")
        
        current_conn_name = None
        if code == 0 and out:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 3 and parts[2] == CLIENT_IFACE:
                    conn_name = parts[0]
                    # Sanitize connection name
                    safe_conn_name = sanitize_connection_name(conn_name)
                    if safe_conn_name:
                        current_conn_name = safe_conn_name
                        break
        
        if not current_conn_name:
            return jsonify({"ok": False, "error": "No active connection"}), 404
        
        # Disconnect and delete the connection
        code, _, _ = run(f"nmcli connection delete {shlex.quote(current_conn_name)}")
        
        if code == 0:
            return jsonify({"ok": True, "message": "Disconnected and forgot current network"})
        else:
            return jsonify({"ok": False, "error": "Failed to disconnect"}), 500
    
    except Exception as e:
        print(f"Error in api_disconnect_current: {e}")  # Log to server only
        return jsonify({"ok": False, "error": "Failed to disconnect"}), 500

@app.post("/api/change-ap-password")
def api_change_ap_password():
    """Change AP password in hostapd configuration"""
    data = request.get_json(silent=True) or {}
    new_password = (data.get("password") or "").strip()
    
    # Sanitize and validate password
    sanitized_password = sanitize_password(new_password)
    
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
        import os
        os.chmod(hostapd_conf, 0o600)
        
        # Restart hostapd to apply changes
        run("sudo systemctl restart hostapd", timeout=10)
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
