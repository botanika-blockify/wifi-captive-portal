import os, subprocess, shlex
from flask import Flask, request, jsonify, send_from_directory, redirect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
WIFI_IFACE = "wlan0"

app = Flask(__name__, static_folder=None)

def run(cmd: str):
    p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out.strip(), err.strip()

@app.get("/api/scan")
def api_scan():
    code, out, err = run("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list")
    networks = []
    if code == 0 and out:
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                security = parts[-1]
                signal = parts[-2]
                ssid = ":".join(parts[:-2])
                if ssid:
                    networks.append({"ssid": ssid, "signal": int(signal) if signal.isdigit() else None, "security": security})
    return jsonify({"ok": True, "networks": networks})

@app.post("/api/connect")
def api_connect():
    data = request.get_json(silent=True) or {}
    ssid = (data.get("ssid") or "").strip()
    pwd = (data.get("password") or "").strip()
    
    if not ssid:
        return jsonify({"ok": False, "error": "SSID required"}), 400
    
    # Escape single quotes in SSID and password for shell safety
    ssid_escaped = ssid.replace("'", "'\\''")
    pwd_escaped = pwd.replace("'", "'\\''") if pwd else ""
    
    if pwd:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' password '{pwd_escaped}' ifname {WIFI_IFACE}"
    else:
        cmd = f"nmcli dev wifi connect '{ssid_escaped}' ifname {WIFI_IFACE}"
    
    code, out, err = run(cmd)
    
    # Improved error detection
    if code == 0:
        return jsonify({"ok": True, "stdout": out, "stderr": err})
    else:
        # Better error message parsing
        error_msg = err.lower() if err else out.lower()
        if any(word in error_msg for word in ["secrets", "password", "wrong", "incorrect"]):
            return jsonify({"ok": False, "error": "wrong_password", "stderr": err, "stdout": out}), 400
        elif "not found" in error_msg:
            return jsonify({"ok": False, "error": "network_not_found", "stderr": err, "stdout": out}), 400
        else:
            return jsonify({"ok": False, "error": "connection_failed", "stderr": err, "stdout": out}), 400

@app.get("/api/status")
def api_status():
    code_ip, out_ip, _ = run(f"ip -br addr show dev {WIFI_IFACE}")
    code_rt, out_rt, _ = run("ip route show default")
    code_ping, _, _ = run("ping -c1 -w2 8.8.8.8")
    return jsonify({"ok": True, "iface": WIFI_IFACE, "ip": out_ip, "default_route": out_rt, "internet": (code_ping == 0)})

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

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_frontend(path):
    return send_from_directory(FRONTEND_DIR, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)