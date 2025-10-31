# /userdata/wifi-captive-portal/backend/app.py
import os
import time
import atexit
import signal
import sys
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

from config import Config
from utils import run_command, validate_ssid, validate_password
from virtual_ap_manager import VirtualAPManager

app = Flask(__name__, static_folder=None)

# Khởi tạo Virtual AP Manager
virtual_ap = VirtualAPManager()

def initialize_virtual_ap():
    """Khởi tạo Virtual AP khi ứng dụng start"""
    try:
        app.logger.info("Initializing Virtual AP...")
        
        # Chờ một chút để hệ thống network sẵn sàng
        time.sleep(3)
        
        success = virtual_ap.start_virtual_ap()
        if success:
            app.logger.info("Virtual AP started successfully")
        else:
            app.logger.error("Failed to start Virtual AP")
            
        return success
        
    except Exception as e:
        app.logger.error(f"Error initializing Virtual AP: {e}")
        return False

def cleanup_virtual_ap():
    """Dọn dẹp khi ứng dụng dừng"""
    try:
        app.logger.info("Cleaning up Virtual AP...")
        virtual_ap.stop_virtual_ap()
        app.logger.info("Virtual AP cleaned up successfully")
    except Exception as e:
        app.logger.error(f"Error cleaning up Virtual AP: {e}")

def signal_handler(signum, frame):
    """Xử lý signal để dọn dẹp đúng cách"""
    app.logger.info(f"Received signal {signum}, cleaning up...")
    cleanup_virtual_ap()
    sys.exit(0)

# Đăng ký signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Đăng ký cleanup function
atexit.register(cleanup_virtual_ap)

# Khởi tạo Virtual AP khi import
app.before_first_request(initialize_virtual_ap)

def restore_ap_mode():
    """Khôi phục AP mode trên virtual interface"""
    try:
        # Dừng kết nối client nếu có
        run_command("nmcli con down $(nmcli -t -f NAME con show --active | head -1)", timeout=10)
        time.sleep(3)
        
        # Khởi động lại virtual AP
        success = virtual_ap.start_virtual_ap()
        
        if success:
            app.logger.info("AP mode restored on virtual interface")
        else:
            app.logger.error("Failed to restore AP mode")
            
        return success
        
    except Exception as e:
        app.logger.error(f"Error in restore_ap_mode: {e}")
        return False

# Các API endpoints giữ nguyên...
@app.get("/api/scan")
def api_scan():
    try:
        code, out, err = run_command("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list", 
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
    
    ssid_escaped = ssid.replace("'", "'\\''")
    pwd_escaped = pwd.replace("'", "'\\''") if pwd else ""
    
    if pwd:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' password '{pwd_escaped}' ifname {Config.WIFI_IFACE}"
    else:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' ifname {Config.WIFI_IFACE}"
    
    connection_success = False
    connection_error = "Unable to join this network"
    
    for attempt in range(Config.MAX_CONNECTION_ATTEMPTS):
        code, out, err = run_command(cmd, timeout=Config.CONNECTION_TIMEOUT)
        
        if code == 0:
            connection_success = True
            break
        
        error_output = (out + " " + err).lower()
        if any(keyword in error_output for keyword in ["secrets", "password", "802.11", "auth"]):
            connection_error = "Incorrect password"
            break
        elif "no network" in error_output or "not found" in error_output:
            connection_error = "Network not available"
            break
        
        if attempt < Config.MAX_CONNECTION_ATTEMPTS - 1:
            time.sleep(2)
    
    if connection_success:
        # KHÔNG restore AP mode - giữ nguyên kết nối client, virtual AP vẫn chạy
        return jsonify({
            "ok": True, 
            "message": "Connected successfully. Captive portal remains available."
        }), 200
    else:
        # Chỉ restore AP khi kết nối thất bại
        restore_success = restore_ap_mode()
        
        if restore_success:
            connection_error += ". AP mode has been restored."
        else:
            connection_error += ". AP mode restoration may be needed."
            
        return jsonify({
            "ok": False, 
            "error": connection_error,
            "ap_restored": restore_success
        }), 400

@app.get("/api/status")
def api_status():
    try:
        code_ip, out_ip, _ = run_command(f"ip -br addr show dev {Config.WIFI_IFACE}")
        code_rt, out_rt, _ = run_command("ip route show default")
        code_ping, _, _ = run_command("ping -c1 -w2 8.8.8.8")
        code_conn, out_conn, _ = run_command("nmcli -t connection show --active")
        
        return jsonify({
            "ok": True, 
            "iface": Config.WIFI_IFACE,
            "ip": out_ip,
            "default_route": out_rt,
            "internet": code_ping == 0,
            "active_connections": out_conn
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

@app.get("/api/restore-ap")
def api_restore_ap():
    success = restore_ap_mode()
    if success:
        return jsonify({"ok": True, "message": "AP mode restored successfully"})
    else:
        return jsonify({"ok": False, "error": "Failed to restore AP mode"}), 500

@app.get("/api/virtual-ap-status")
def api_virtual_ap_status():
    """API kiểm tra trạng thái Virtual AP"""
    try:
        code, out, err = run_command(f"ip link show {Config.VIRTUAL_IFACE}")
        virtual_iface_exists = code == 0
        
        code, out, err = run_command("pgrep hostapd")
        hostapd_running = code == 0
        
        return jsonify({
            "ok": True,
            "virtual_interface": virtual_iface_exists,
            "hostapd_running": hostapd_running,
            "virtual_iface": Config.VIRTUAL_IFACE,
            "physical_iface": Config.WIFI_IFACE
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Các captive portal endpoints giữ nguyên...
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
    return send_from_directory(Config.FRONTEND_DIR, "index.html")

@app.route("/success.html")
def serve_success():
    return send_from_directory(Config.FRONTEND_DIR, "success.html")

@app.route("/public/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(Config.FRONTEND_DIR, "public"), filename)

@app.route("/<path:path>")
def serve_frontend(path):
    if os.path.exists(os.path.join(Config.FRONTEND_DIR, path)):
        return send_from_directory(Config.FRONTEND_DIR, path)
    return send_from_directory(Config.FRONTEND_DIR, "index.html")

if __name__ == "__main__":
    # Khởi tạo Virtual AP ngay khi chạy ứng dụng
    init_success = initialize_virtual_ap()
    
    if init_success:
        print("Virtual AP initialized successfully, starting Flask app...")
        app.run(host="0.0.0.0", port=80, debug=False)
    else:
        print("Failed to initialize Virtual AP, exiting...")
        sys.exit(1)