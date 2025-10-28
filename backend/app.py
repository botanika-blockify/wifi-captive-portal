import os, subprocess, shlex
import time
from flask import Flask, request, jsonify, send_from_directory, redirect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
WIFI_IFACE = "wlan0"

app = Flask(__name__, static_folder=None)

class Config:
    MAX_CONNECTION_ATTEMPTS = 1
    CONNECTION_TIMEOUT = 30
    SCAN_TIMEOUT = 10

def run(cmd: str, timeout=30):
    """Run command with timeout"""
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
    """Validate SSID to prevent injection attacks"""
    if not ssid or len(ssid) > 32:
        return False
    import re
    if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', ssid):
        return False
    return True

def validate_password(password):
    """Validate password length"""
    if password and len(password) > 64:
        return False
    return True

@app.get("/api/scan")
def api_scan():
    """Scan for available Wi-Fi networks"""
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
        
        # Sort by signal strength (strongest first)
        networks.sort(key=lambda x: x["signal"] or 0, reverse=True)
        return jsonify({"ok": True, "networks": networks})
    
    except Exception as e:
        return jsonify({"ok": False, "error": "Scan failed"}), 500

@app.post("/api/connect")
def api_connect():
    """Connect to Wi-Fi network"""
    data = request.get_json(silent=True) or {}
    ssid = (data.get("ssid") or "").strip()
    pwd = (data.get("password") or "").strip()
    
    if not ssid:
        return jsonify({"ok": False, "error": "SSID required"}), 400
    
    if not validate_ssid(ssid):
        return jsonify({"ok": False, "error": "Invalid SSID"}), 400
        
    if not validate_password(pwd):
        return jsonify({"ok": False, "error": "Invalid password"}), 400
    
    ssid_escaped = ssid.replace("'", "'\\''")
    pwd_escaped = pwd.replace("'", "'\\''") if pwd else ""
    
    if pwd:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' password '{pwd_escaped}' ifname {WIFI_IFACE}"
    else:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' ifname {WIFI_IFACE}"
    
    for attempt in range(Config.MAX_CONNECTION_ATTEMPTS):
        code, out, err = run(cmd, timeout=Config.CONNECTION_TIMEOUT)
        
        if code == 0:
            return jsonify({
                "ok": True, 
                "message": "Connected successfully",
                "attempts": attempt + 1
            }), 200
        
        if attempt < Config.MAX_CONNECTION_ATTEMPTS - 1:
            time.sleep(2)
    
    return jsonify({
        "ok": False, 
        "error": "Unable to join this network",
        "attempts": Config.MAX_CONNECTION_ATTEMPTS}), 400

@app.get("/api/status")
def api_status():
    """Get current connection status"""
    try:
        # Get IP address
        code_ip, out_ip, _ = run(f"ip -br addr show dev {WIFI_IFACE}")
        
        # Get default route
        code_rt, out_rt, _ = run("ip route show default")
        
        # Check internet connectivity
        code_ping, _, _ = run("ping -c1 -w2 8.8.8.8")
        
        # Get current connection info
        code_conn, out_conn, _ = run("nmcli -t connection show --active")
        
        return jsonify({
            "ok": True, 
            "iface": WIFI_IFACE,
            "ip": out_ip,
            "default_route": out_rt,
            "internet": code_ping == 0,
            "active_connections": out_conn
        })
    
    except Exception as e:
        return jsonify({"ok": False, "error": "Status check failed"}), 500

@app.get("/api/health")
def api_health():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "wifi-portal",
        "timestamp": time.time(),
        "version": "1.0.0"
    })

@app.get("/generate_204")
@app.get("/gen_204")
@app.get("/library/test/success.html")
@app.get("/hotspot-detect.html")
@app.get("/hotspot-detect")
@app.get("/ncsi.txt")
@app.get("/connecttest.txt")
@app.get("/redirect")
def captive_probes():
    return redirect("/", code=302)

@app.route("/")
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