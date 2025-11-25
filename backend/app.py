import os, subprocess, shlex
import time
import tempfile
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
AP_IFACE = "wlP2p33s0"      
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

def manage_ap_mode(action="stop"):
    try:
        if action == "stop":
            run("sudo systemctl stop hostapd", timeout=10)
            run("sudo systemctl stop dnsmasq", timeout=10)
            run("sudo pkill hostapd", timeout=5)
            time.sleep(2)
            return True
        elif action == "start":
            run("sudo systemctl start hostapd", timeout=10)
            run("sudo systemctl start dnsmasq", timeout=10)
            time.sleep(3)
            return True
    except Exception as e:
        print(f"AP management error: {e}")
        return False

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
        if not is_client_connected():
            manage_ap_mode("stop")
            time.sleep(2)
        
        run(f"nmcli device set {CLIENT_IFACE} managed yes", timeout=5)
        time.sleep(1)
        
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
        
        if not is_client_connected():
            manage_ap_mode("start")
        
        return jsonify({"ok": True, "networks": networks})
    
    except Exception as e:
        if not is_client_connected():
            manage_ap_mode("start")
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
    
    ap_stopped = manage_ap_mode("stop")
    
    if not ap_stopped:
        return jsonify({"ok": False, "error": "Cannot stop AP mode"}), 500
    
    run(f"nmcli device set {CLIENT_IFACE} managed yes", timeout=5)
    time.sleep(2)
    
    connection_success = False
    connection_error = "Unable to join this network"
    detailed_error = ""
    
    ssid_escaped = shlex.quote(ssid)
    pwd_escaped = shlex.quote(pwd) if pwd else ""
    
    if pwd:
        cmd = f"nmcli --wait 30 dev wifi connect {ssid_escaped} password {pwd_escaped} ifname {CLIENT_IFACE}"
    else:
        cmd = f"nmcli --wait 30 dev wifi connect {ssid_escaped} ifname {CLIENT_IFACE}"
    
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
            
            run(f"sudo pkill wpa_supplicant", timeout=5)
            time.sleep(2)
            
            cmd = f"sudo wpa_supplicant -B -i {CLIENT_IFACE} -c {temp_config}"
            code, out, err = run(cmd, timeout=10)
            
            if code == 0:
                time.sleep(5)
                
                run(f"sudo dhclient -v {CLIENT_IFACE}", timeout=15)
                
                code_check, out_check, _ = run(f"iwconfig {CLIENT_IFACE}", timeout=5)
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
            "message": "Connected successfully - AP mode disabled"
        }), 200
    else:
        ap_restarted = manage_ap_mode("start")
        if not ap_restarted:
            connection_error += " (Failed to restart AP)"
        
        return jsonify({
            "ok": False, 
            "error": connection_error,
            "details": detailed_error
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

@app.post("/api/enable-ap")
def api_enable_ap():
    try:
        if not is_client_connected():
            success = manage_ap_mode("start")
            if success:
                return jsonify({"ok": True, "message": "AP mode enabled"})
            else:
                return jsonify({"ok": False, "error": "Failed to enable AP mode"}), 500
        else:
            return jsonify({"ok": False, "error": "Cannot enable AP - client is connected"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/disable-ap")
def api_disable_ap():
    try:
        success = manage_ap_mode("stop")
        if success:
            return jsonify({"ok": True, "message": "AP mode disabled"})
        else:
            return jsonify({"ok": False, "error": "Failed to disable AP mode"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/health")
def api_health():
    client_connected = is_client_connected()
    return jsonify({
        "status": "healthy",
        "service": "wifi-portal",
        "timestamp": time.time(),
        "version": "1.0.0",
        "ap_mode": not client_connected,
        "client_connected": client_connected
    })

@app.post("/api/debug-connect")
def api_debug_connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid", "").strip()
    
    cmd_scan = f"nmcli -f SSID,BSSID,MODE,CHAN,FREQ,RATE,SIGNAL,SECURITY dev wifi list ifname {CLIENT_IFACE}"
    code_scan, out_scan, err_scan = run(cmd_scan, timeout=10)
    
    cmd_iface = f"ip addr show {CLIENT_IFACE}"
    code_iface, out_iface, err_iface = run(cmd_iface)
    
    cmd_conn = "nmcli -t connection show --active"
    code_conn, out_conn, err_conn = run(cmd_conn)
    
    cmd_ap = "sudo systemctl status hostapd"
    code_ap, out_ap, err_ap = run(cmd_ap)
    
    debug_info = {
        "ssid_requested": ssid,
        "client_interface": CLIENT_IFACE,
        "ap_interface": AP_IFACE,
        "ap_status": out_ap,
        "available_networks": out_scan,
        "interface_status": out_iface,
        "current_connections": out_conn,
        "scan_error": err_scan,
        "iface_error": err_iface,
        "client_connected": is_client_connected()
    }
    
    return jsonify(debug_info)

@app.get("/api/forget-all")
def api_forget_all():
    try:
        code, out, err = run("nmcli -t -f NAME,UUID connection show")
        if code == 0:
            for line in out.splitlines():
                if "wifi" in line.lower():
                    parts = line.split(":")
                    if len(parts) >= 2:
                        conn_name = parts[0]
                        run(f"nmcli connection delete '{conn_name}'")
        
        run("sudo systemctl restart NetworkManager", timeout=10)
        time.sleep(3)
        
        manage_ap_mode("start")
        
        return jsonify({"ok": True, "message": "Forgot all WiFi connections"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/generate_204")
def generate_204():
    if is_client_connected():
        return "", 204
    else:
        return redirect("/", code=302)

@app.get("/gen_204")
def gen_204():
    if is_client_connected():
        return "", 204
    else:
        return redirect("/", code=302)

@app.get("/library/test/success.html")
def library_test_success():
    return redirect("/", code=302)

@app.get("/hotspot-detect.html")
def hotspot_detect_html():
    if is_client_connected():
        return "", 204
    else:
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
    if is_client_connected():
        return "", 204
    else:
        return redirect("/", code=302)

@app.get("/ncsi.txt")
def ncsi_txt():
    if is_client_connected():
        return Response("Microsoft NCSI", mimetype='text/plain')
    else:
        return redirect("/", code=302)

@app.get("/connecttest.txt")
def connecttest_txt():
    if is_client_connected():
        return Response("success", mimetype='text/plain')
    else:
        return redirect("/", code=302)

@app.get("/redirect")
def redirect_captive():
    if is_client_connected():
        return "", 204
    else:
        return redirect("/", code=302)

@app.get("/captiveportal")
def captiveportal():
    if is_client_connected():
        return "", 204

    else:
        return redirect("/", code=302)

@app.get("/fs/captiveportal")
def fs_captiveportal():
    if is_client_connected():
        return "", 204
    else:
        return redirect("/", code=302)

@app.get("/success.txt")
def success_txt():
    if is_client_connected():
        return Response("success", mimetype='text/plain')
    else:
        return redirect("/", code=302)

@app.get("/canonical.html")
def canonical_html():
    if is_client_connected():
        return "", 204
    else:
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
    app.run(host="192.168.4.1", port=80, threaded=True)
