import os, subprocess, shlex
import time
import tempfile
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
WIFI_IFACE = "wlan0"

app = Flask(__name__, static_folder=None)

class Config:
    MAX_CONNECTION_ATTEMPTS = 3
    CONNECTION_TIMEOUT = 45
    SCAN_TIMEOUT = 15

def run(cmd: str, timeout=30):
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
    if not re.match(r'^[a-zA-Z0-9_\-\.\s\u0080-\uFFFF]+$', ssid):
        return False
    return True

def validate_password(password):
    if password and len(password) > 64:
        return False
    return True

def get_wifi_security_type(ssid):
    """Xác định loại bảo mật của mạng WiFi"""
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
        code, out, err = run("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list", 
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
    
    connection_success = False
    connection_error = "Unable to join this network"
    detailed_error = ""
    
    ssid_escaped = shlex.quote(ssid)
    pwd_escaped = shlex.quote(pwd) if pwd else ""
    
    if pwd:
        cmd = f"nmcli --wait 30 dev wifi connect {ssid_escaped} password {pwd_escaped} ifname {WIFI_IFACE}"
    else:
        cmd = f"nmcli --wait 30 dev wifi connect {ssid_escaped} ifname {WIFI_IFACE}"
    
    for attempt in range(Config.MAX_CONNECTION_ATTEMPTS):
        code, out, err = run(cmd, timeout=Config.CONNECTION_TIMEOUT)
        
        if code == 0:
            connection_success = True
            break
        
        error_output = (out + " " + err).lower()
        detailed_error = f"Output: {out}, Error: {err}"
        
        if any(keyword in error_output for keyword in ["secrets", "password", "802.11", "auth", "wpa"]):
            connection_error = "Incorrect password"
            break
        elif "no network" in error_output or "not found" in error_output:
            connection_error = "Network not available"
            break
        elif "timeout" in error_output:
            connection_error = "Connection timeout - network may be too far or busy"
        elif "device is busy" in error_output:
            connection_error = "WiFi device is busy, please try again"
            time.sleep(3)
        elif "no secrets" in error_output:
            connection_error = "Password required for this network"
            break
        
        if attempt < Config.MAX_CONNECTION_ATTEMPTS - 1:
            time.sleep(2)
    
    if not connection_success and pwd:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
                f.write(f'''network={{
    ssid="{ssid}"
    scan_ssid=1
    key_mgmt=WPA-PSK
    psk="{pwd}"
}}''')
                temp_config = f.name
            
            run("sudo pkill wpa_supplicant", timeout=5)
            time.sleep(2)
            
            cmd = f"sudo wpa_supplicant -B -i {WIFI_IFACE} -c {temp_config}"
            code, out, err = run(cmd, timeout=10)
            
            if code == 0:
                time.sleep(5)
                
                run(f"sudo dhclient -v {WIFI_IFACE}", timeout=15)
                
                code_check, out_check, _ = run(f"iwconfig {WIFI_IFACE}", timeout=5)
                if f'ESSID:"{ssid}"' in out_check:
                    connection_success = True
                    connection_error = ""
                else:
                    connection_error = "Connected but SSID mismatch"
            
            if os.path.exists(temp_config):
                os.unlink(temp_config)
                
        except Exception as e:
            if not connection_error:
                connection_error = f"Fallback also failed: {str(e)}"
    
    if connection_success:
        return jsonify({
            "ok": True, 
            "message": "Connected successfully"
        }), 200
    else:
        return jsonify({
            "ok": False, 
            "error": connection_error,
            "details": detailed_error
        }), 400

@app.get("/api/status")
def api_status():
    try:
        code_ip, out_ip, _ = run(f"ip -br addr show dev {WIFI_IFACE}")
        code_rt, out_rt, _ = run("ip route show default")
        code_ping, _, _ = run("ping -c1 -w2 8.8.8.8")
        code_conn, out_conn, _ = run("nmcli -t connection show --active")
        
        code_wifi, out_wifi, _ = run(f"iwconfig {WIFI_IFACE}")
        
        return jsonify({
            "ok": True, 
            "iface": WIFI_IFACE,
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
    return jsonify({
        "status": "healthy",
        "service": "wifi-portal",
        "timestamp": time.time(),
        "version": "1.0.0"
    })

@app.post("/api/debug-connect")
def api_debug_connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid", "").strip()
    
    cmd_scan = f"nmcli -f SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,SECURITY dev wifi list"
    code_scan, out_scan, err_scan = run(cmd_scan, timeout=10)
    
    cmd_iface = f"ip addr show {WIFI_IFACE}"
    code_iface, out_iface, err_iface = run(cmd_iface)
    
    cmd_conn = "nmcli -t connection show --active"
    code_conn, out_conn, err_conn = run(cmd_conn)
    
    debug_info = {
        "ssid_requested": ssid,
        "available_networks": out_scan,
        "interface_status": out_iface,
        "current_connections": out_conn,
        "scan_error": err_scan,
        "iface_error": err_iface
    }
    
    return jsonify(debug_info)

@app.get("/api/forget-all")
def api_forget_all():
    """Quên tất cả kết nối WiFi cũ"""
    try:
        code, out, err = run("nmcli -t -f NAME,UUID connection show")
        if code == 0:
            for line in out.splitlines():
                if "wifi" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        conn_name = parts[0]
                        run(f"nmcli connection delete '{conn_name}'")
        
        # Khởi động lại NetworkManager
        run("sudo systemctl restart NetworkManager", timeout=10)
        time.sleep(3)
        
        return jsonify({"ok": True, "message": "Forgot all WiFi connections"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/generate_204")
def generate_204():
    return "", 204

@app.get("/gen_204")
def gen_204():
    return "", 204

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
    return Response("Microsoft NCSI", mimetype='text/plain')

@app.get("/connecttest.txt")
def connecttest_txt():
    return Response("success", mimetype='text/plain')

@app.get("/redirect")
def redirect_captive():
    return redirect("/", code=302)

@app.get("/captiveportal")
def captiveportal():
    return redirect("/", code=302)

@app.get("/fs/captiveportal")
def fs_captiveportal():
    return "", 204

@app.get("/success.txt")
def success_txt():
    return Response("success", mimetype='text/plain')

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
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/success.html")
def serve_success():
    return send_from_directory(FRONTEND_DIR, "success.html")

@app.route("/public/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "public"), filename)

@app.route("/<path:path>")
def serve_frontend(path):
    if os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)