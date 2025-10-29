import os
import json
import requests
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------
# Config / paths
# ---------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

DEFAULT_CONFIG = {
    "api_base": "https://newptemi-jejj.vercel.app",
    "admin_user": "admin",
    "admin_password_hash": "",  # will set default below
    "auto_try_list_endpoints": [
        "/api/keys",
        "/api/key/list",
        "/api/key/all",
        "/api/keys/list",
        "/keys",
        "/api/list",
        "/api/key/listall"
    ]
}

# ensure config
if not os.path.exists(CONFIG_PATH):
    DEFAULT_CONFIG["admin_password_hash"] = generate_password_hash("admin123")
    with open(CONFIG_PATH, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)

with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

# ensure password hash exists (if user manually put plain password)
if not CONFIG.get("admin_password_hash"):
    CONFIG["admin_password_hash"] = generate_password_hash("admin123")
    with open(CONFIG_PATH, "w") as f:
        json.dump(CONFIG, f, indent=2)

# ---------------------
# Flask app
# ---------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "change_this_secret_for_prod")

# ---------------------
# Helpers
# ---------------------
def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(CONFIG, f, indent=2)

def try_fetch_keys():
    """Try a list of likely endpoints on the configured API base to return keys list.
    Expect JSON list of keys or dict with 'keys' field. Returns (success_bool, data_or_error)"""
    api_base = CONFIG.get("api_base", "").rstrip("/")
    if not api_base:
        return False, "API base not configured."

    endpoints = CONFIG.get("auto_try_list_endpoints", [])
    headers = {"Accept": "application/json"}
    for ep in endpoints:
        url = api_base + ep
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                try:
                    j = r.json()
                except Exception:
                    # maybe it's plain text or not JSON
                    return False, f"Endpoint {url} returned 200 but JSON parse failed."
                # If returned dict with list inside
                if isinstance(j, dict):
                    # Common shapes: {"keys":[...]} or {"data": {"keys":[...]}} or direct mapping
                    if "keys" in j and isinstance(j["keys"], list):
                        return True, j["keys"]
                    if "data" in j and isinstance(j["data"], list):
                        return True, j["data"]
                    # maybe it's already a list-like dict with numeric keys -> convert to list
                    # fallback: try to find a list value
                    for v in j.values():
                        if isinstance(v, list):
                            return True, v
                    # if dict seems like a single key entry, convert to list
                    # but usually listing endpoints return lists
                    # if it's single object, wrap
                    if isinstance(j, dict):
                        return True, [j]
                elif isinstance(j, list):
                    return True, j
                # else continue trying other endpoints
        except Exception as e:
            # try next
            continue
    return False, "No working list endpoint found on API base."

def call_api_create(payload):
    api_base = CONFIG.get("api_base","").rstrip("/")
    if not api_base:
        return False, "API base not configured"
    try:
        r = requests.post(f"{api_base}/api/key/create", json=payload, timeout=20)
        return (r.status_code in (200,201)), r.text if not r.headers.get("content-type","").startswith("application/json") else r.json()
    except Exception as e:
        return False, str(e)

def call_api_delete(key):
    api_base = CONFIG.get("api_base","").rstrip("/")
    if not api_base:
        return False, "API base not configured"
    try:
        r = requests.delete(f"{api_base}/api/key/remove", params={"key": key}, timeout=15)
        return r.status_code == 200, r.text if r.status_code != 200 else r.text
    except Exception as e:
        return False, str(e)

def call_api_update(key, payload):
    api_base = CONFIG.get("api_base","").rstrip("/")
    if not api_base:
        return False, "API base not configured"
    try:
        r = requests.put(f"{api_base}/api/key/update", json=payload, timeout=20)
        return r.status_code == 200, r.text if r.status_code != 200 else r.text
    except Exception as e:
        return False, str(e)

def call_api_check(key):
    api_base = CONFIG.get("api_base","").rstrip("/")
    if not api_base:
        return False, "API base not configured"
    try:
        r = requests.get(f"{api_base}/api/key/check", params={"key": key}, timeout=12)
        if r.status_code == 200:
            try:
                return True, r.json()
            except:
                return True, r.text
        else:
            return False, r.text
    except Exception as e:
        return False, str(e)

def days_left_for_date(datestr):
    """Try to parse date string in common formats and return days left (int)."""
    if not datestr:
        return ""
    # try iso first
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y.%m.%d"):
        try:
            dt = datetime.fromisoformat(datestr) if "T" in datestr else datetime.strptime(datestr, fmt)
            delta = dt.date() - date.today()
            return max(delta.days, 0)
        except Exception:
            continue
    # last fallback: try to extract year-month-day digits
    try:
        parts = [int(p) for p in datestr.replace("-", " ").replace("/", " ").split() if p.isdigit() and len(p) >= 2]
        if len(parts) >= 3:
            y,m,d = parts[0], parts[1], parts[2]
            dt = date(y,m,d)
            delta = dt - date.today()
            return max(delta.days, 0)
    except Exception:
        pass
    return ""

# ---------------------
# Auth (very light)
# ---------------------
def logged_in():
    return session.get("admin_logged_in", False)

@app.route("/login", methods=["GET","POST"])
def login():
    if logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        user = request.form.get("username","").strip()
        pwd = request.form.get("password","").strip()
        if user == CONFIG.get("admin_user") and check_password_hash(CONFIG.get("admin_password_hash",""), pwd):
            session["admin_logged_in"] = True
            session["admin_user"] = user
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------------
# Static files (optional)
# ---------------------
@app.route('/static/<path:p>')
def static_proxy(p):
    return send_from_directory(STATIC_DIR, p)

# ---------------------
# Pages
# ---------------------
@app.route("/")
def index():
    if not logged_in():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template("dashboard.html", api_base=CONFIG.get("api_base",""))

@app.route("/settings", methods=["GET","POST"])
def settings():
    if not logged_in():
        return redirect(url_for("login"))
    if request.method == "POST":
        api_base = request.form.get("api_base","").strip()
        admin_user = request.form.get("admin_user","").strip()
        admin_pass = request.form.get("admin_pass","").strip()
        CONFIG["api_base"] = api_base or CONFIG.get("api_base")
        if admin_user:
            CONFIG["admin_user"] = admin_user
        if admin_pass:
            CONFIG["admin_password_hash"] = generate_password_hash(admin_pass)
        save_config()
        flash("Settings saved", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", cfg=CONFIG)

# ---------------------
# API proxy endpoints for UI AJAX
# ---------------------
@app.route("/api/keys", methods=["GET"])
def api_keys():
    if not logged_in():
        return jsonify({"error": "not logged in"}), 401
    ok, data = try_fetch_keys()
    if not ok:
        return jsonify({"error": data}), 500
    # normalize list items to have key, total_requests, remaining_requests, expires_at fields if possible
    normalized = []
    for item in data:
        # item might be a dict from remote API with different field names
        if isinstance(item, dict):
            keyname = item.get("key") or item.get("key_value") or item.get("value") or item.get("Key") or item.get("KeyName") or item.get("name")
            total = item.get("total_requests") or item.get("total") or item.get("TotalRequests") or item.get("requests_total")
            remaining = item.get("remaining_requests") or item.get("remaining") or item.get("RemainingRequests") or item.get("requests_remaining")
            expires = item.get("expires_at") or item.get("expiry") or item.get("expires") or item.get("ExpiresAt")
            # sometimes like "500/600" in a single field
            request_field = item.get("requests") or item.get("Request") or item.get("RequestCount")
            if request_field and isinstance(request_field, str) and "/" in request_field:
                parts = request_field.split("/")
                try:
                    remaining = int(parts[0].strip())
                    total = int(parts[1].strip())
                except:
                    pass
            normalized.append({
                "key": keyname or str(item),
                "total": int(total) if isinstance(total,(int,str)) and str(total).isdigit() else (int(total) if isinstance(total,int) else (None)),
                "remaining": int(remaining) if isinstance(remaining,(int,str)) and str(remaining).isdigit() else (int(remaining) if isinstance(remaining,int) else None),
                "expires_at": expires or "",
                "raw": item
            })
        else:
            normalized.append({"key": str(item), "total": None, "remaining": None, "expires_at": "", "raw": item})
    return jsonify({"keys": normalized})

@app.route("/api/key/create", methods=["POST"])
def api_create_key():
    if not logged_in():
        return jsonify({"error":"not logged in"}), 401
    data = request.get_json() or {}
    # expected fields: custom_key, total_requests, expiry_days, notes
    payload = {
        "custom_key": data.get("custom_key"),
        "total_requests": data.get("total_requests"),
        "expiry_days": data.get("expiry_days"),
        "notes": data.get("notes", "")
    }
    ok, res = call_api_create(payload)
    if not ok:
        return jsonify({"error": str(res)}), 500
    return jsonify({"ok": True, "result": res})

@app.route("/api/key/delete", methods=["POST"])
def api_delete_key():
    if not logged_in():
        return jsonify({"error":"not logged in"}), 401
    key = request.json.get("key")
    if not key:
        return jsonify({"error":"missing key"}), 400
    ok, res = call_api_delete(key)
    if not ok:
        return jsonify({"error": str(res)}), 500
    return jsonify({"ok": True, "result": res})

@app.route("/api/key/update", methods=["POST"])
def api_update_key():
    """Update key through remote API. Expect 'key' + update fields in JSON"""
    if not logged_in():
        return jsonify({"error":"not logged in"}), 401
    data = request.get_json() or {}
    if "key" not in data:
        return jsonify({"error":"missing key"}), 400
    ok, res = call_api_update(data.get("key"), data)
    if not ok:
        return jsonify({"error": str(res)}), 500
    return jsonify({"ok": True, "result": res})

@app.route("/api/key/check", methods=["GET"])
def api_check_key():
    if not logged_in():
        return jsonify({"error":"not logged in"}), 401
    key = request.args.get("key")
    if not key:
        return jsonify({"error":"missing key"}), 400
    ok, res = call_api_check(key)
    if not ok:
        return jsonify({"error": str(res)}), 500
    return jsonify({"ok": True, "result": res})

# ---------------------
# Run
# ---------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)