from flask import Flask, render_template, render_template_string, request, redirect, url_for, session, jsonify, send_file
import os, zipfile, subprocess, shutil, json, time, io, signal

app = Flask(__name__)
app.secret_key = "jubayer_hosting_v5_final_pro"

UPLOAD_FOLDER = os.path.abspath("uploads")
DB_FILE = "database.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

processes = {}
file_handles = {}  # লগ ফাইলের হ্যান্ডেল ট্র্যাক রাখার জন্য

def load_db():
    if not os.path.exists(DB_FILE):
        default = {"user_pw": "codex123", "users": {}, "start_times": {}}
        with open(DB_FILE, "w") as f: json.dump(default, f)
        return default
    with open(DB_FILE, "r") as f:
        try:
            data = json.load(f)
            if "users" not in data: data["users"] = {}
            if "user_pw" not in data: data["user_pw"] = "lam codex"
            if "start_times" not in data: data["start_times"] = {}
            return data
        except:
            return {"user_pw": "codex123", "users": {}, "start_times": {}}

def save_db(data):
    temp_db = DB_FILE + ".tmp"
    with open(temp_db, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(temp_db, DB_FILE)

ADMIN_PASS = "5656"

# --- PATH TRAVERSAL PROTECTION FUNCTION ---
def is_safe_path(base_dir, path, follow_symlinks=True):
    if follow_symlinks:
        matchpath = os.path.realpath(path)
    else:
        matchpath = os.path.abspath(path)
    return base_dir == os.path.commonpath((base_dir, matchpath))

# --- LOGIN PAGE HTML ---
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login | LAM CODEX</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <script language="javascript">
document.write(unescape('%3Cscript%20src%3D%22https%3A%2F%2Fpl28664877.effectivegatecpm.com%2F9b%2F09%2F14%2F9b0914dde54e0f75462c782bc760cb71.js%22%3E%3C%2Fscript%3E'));
</script>

    <style>
        :root { 
            --bg: #030508; 
            --glass: rgba(10, 15, 26, 0.8); 
        }
        body { 
            background: var(--bg); 
            color: white; 
            font-family: 'Orbitron', sans-serif; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            margin: 0; 
            overflow: hidden; 
        }
        #particles-js { 
            position: fixed; 
            width: 100%; 
            height: 100%; 
            z-index: 1; 
        }
        
        /* --- Animated RGB Border Container --- */
        .rgb-border-box {
            position: relative;
            z-index: 10;
            padding: 4px; 
            border-radius: 25px;
            background: linear-gradient(0deg, #00ff00, #00ff66, #00ffff, #ff0055, #00ff00);
            background-size: 400% 400%;
            animation: rgbShift 2s linear infinite; 
            box-shadow: 0 0 40px rgba(0, 255, 100, 0.4);
        }

        /* --- Login Card Inside --- */
        .login-card { 
            background: var(--glass); 
            padding: 40px 30px; 
            border-radius: 23px; 
            width: 340px; 
            text-align: center; 
            backdrop-filter: blur(25px); 
            box-shadow: inset 0 0 20px rgba(255, 255, 255, 0.05);
        }
        
        /* --- Fast RGB Keyframes --- */
        @keyframes rgbShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* --- Lock Icon Container with RGB Pulse --- */
        .lock-container { 
            width: 80px; 
            height: 80px; 
            background: rgba(255, 255, 255, 0.05); 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            margin: 0 auto 20px; 
            position: relative;
        }
        .lock-container::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            border-radius: 50%;
            background: linear-gradient(45deg, #00ff00, #00ffff, #ff0055);
            z-index: -1;
            animation: rgbShift 1.5s linear infinite;
        }
        .lock-icon { font-size: 35px; color: #fff; text-shadow: 0 0 10px rgba(255,255,255,0.8); }
        
        h2 { 
            font-size: 20px; 
            margin-bottom: 25px; 
            letter-spacing: 4px; 
            text-transform: uppercase; 
            background: linear-gradient(to right, #00ff66, #00ffff); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
            font-weight: bold;
        }
        
        /* --- Inputs with Fast RGB Border --- */
        input, select { 
            width: 100%; 
            padding: 14px; 
            margin: 12px 0; 
            border-radius: 12px; 
            border: 2px solid transparent; 
            background: linear-gradient(rgba(10, 15, 26, 0.9), rgba(10, 15, 26, 0.9)) padding-box,
                        linear-gradient(45deg, #ff0000, #00ff00, #0000ff, #00ffff, #ff00ff) border-box;
            background-size: 300% 300%;
            animation: rgbShift 2s linear infinite;
            color: #fff; 
            outline: none; 
            font-size: 14px; 
            transition: 0.3s; 
            box-sizing: border-box;
        }
        input:focus, select:focus { 
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.6); 
            background: linear-gradient(rgba(20, 30, 50, 0.9), rgba(20, 30, 50, 0.9)) padding-box,
                        linear-gradient(45deg, #00ff00, #00ffff, #ff00ff, #ff0000) border-box;
            background-size: 300% 300%;
        }
        
        /* --- RGB Button --- */
        button { 
            width: 100%; 
            padding: 15px; 
            border-radius: 12px; 
            border: none; 
            background: linear-gradient(45deg, #00ff00, #00ffff, #ff0055); 
            background-size: 200% auto;
            color: #fff; 
            font-weight: bold; 
            font-size: 15px; 
            cursor: pointer; 
            margin-top: 15px; 
            text-transform: uppercase; 
            letter-spacing: 2px; 
            transition: 0.4s; 
            animation: rgbShift 1.5s infinite linear;
        }
        button:hover { 
            letter-spacing: 4px; 
            box-shadow: 0 0 25px rgba(0, 255, 100, 0.8); 
        }
        .get-pw { margin-top: 25px; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px; }
        .get-pw a { color: #00ffff; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 8px; transition: 0.3s; }
        .get-pw a:hover { text-shadow: 0 0 10px #00ffff; }
    </style>
</head>
<body>
    <div id="particles-js"></div>
    
    <div class="rgb-border-box">
        <div class="login-card">
            <div class="lock-container"><i class="fa-solid fa-user-shield lock-icon"></i></div>
            <h2>System Login</h2>
            <form method="post" action="/login">
                <select name="login_type">
                    <option value="user">USER ACCESS</option>
                    <option value="admin">ADMIN ROOT</option>
                </select>
                <input type="text" name="username" placeholder="Enter Nickname" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Access System</button>
            </form>
            <div class="get-pw"><a href="https://t.me/mr_ghost34" target="_blank"><i class="fa-brands fa-telegram"></i> FORGOT PASSWORD?</a></div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/particles.js/2.0.0/particles.min.js"></script>
    <script>
        particlesJS('particles-js', {
          "particles": {
            "number": { "value": 120, "density": { "enable": true, "value_area": 800 } },
            "color": { "value": ["#00ff00", "#00ff66", "#00ffff", "#ff0055", "#3333ff"] },
            "shape": { 
                "type": ["circle", "triangle", "polygon"], 
                "polygon": { "nb_sides": 5 } 
            },
            "opacity": { "value": 0.7, "random": true, "anim": { "enable": true, "speed": 1.5, "opacity_min": 0.3, "sync": false } },
            "size": { "value": 8, "random": true, "anim": { "enable": true, "speed": 6, "size_min": 2, "sync": false } },
            "line_linked": { 
                "enable": true, 
                "distance": 130, 
                "color": "#00ff66", 
                "opacity": 0.3, 
                "width": 1.5 
            },
            "move": { 
                "enable": true, 
                "speed": 4.5, 
                "direction": "none", 
                "random": true, 
                "straight": false, 
                "out_mode": "out", 
                "bounce": false,
                "attract": { "enable": true, "rotateX": 600, "rotateY": 1200 }
            }
        },
          "interactivity": {
            "detect_on": "canvas",
            "events": { "onhover": { "enable": true, "mode": "grab" }, "onclick": { "enable": true, "mode": "push" }, "resize": true },
            "modes": { "grab": { "distance": 180, "line_linked": { "opacity": 0.6 } }, "push": { "particles_nb": 4 } }
          },
          "retina_detect": true
        });
    </script>
</body>
</html>
'''

# --- ADMIN PANEL HTML ---
ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Root | Ultra Hosting</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --bg: #030508; --card: rgba(22, 27, 34, 0.8); --accent: #00ffff; --text: #e6edf3; --glass: rgba(255, 255, 255, 0.05); }
        * { box-sizing: border-box; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 15px; min-height: 100vh; overflow-x: hidden; position:[...]
        .bg-layer { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; overflow: hidden; background: radial-gradient(circle at center, #0a0b10 0%, #000 100%); }
        .bg-layer::before { content: ''; position: absolute; width: 200%; height: 200%; background: conic-gradient(from 0deg at 50% 50%, #00ffff10, #7000ff10, #00ffff10); animation: rotateMesh 20[...]
        .orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.3; animation: float 10s infinite alternate; }
        .orb-1 { width: 300px; height: 300px; background: var(--accent); top: -10%; left: -10%; }
        .orb-2 { width: 250px; height: 250px; background: #7000ff; bottom: -5%; right: -5%; animation-delay: -2s; }
        @keyframes rotateMesh { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes float { from { transform: translate(0,0); } to { transform: translate(30px, 50px); } }
        .header { display: flex; flex-direction: row; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 10px; background: var(--glass); border-radius: 15px; backd[...]
        .header h2 { font-size: 18px; color: var(--accent); margin: 0; letter-spacing: 1px; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .stat-card { background: var(--card); padding: 15px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.05); text-align: center; backdrop-filter: blur(5px); }
        .stat-card i { font-size: 20px; color: var(--accent); margin-bottom: 5px; }
        .stat-card p { font-size: 12px; margin: 5px 0; opacity: 0.7; }
        .stat-card div { font-size: 18px; font-weight: bold; }
        .card { background: var(--card); padding: 15px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 20px; backdrop-filte[...]
        h3 { margin-top: 0; font-size: 16px; color: var(--accent); display: flex; align-items: center; gap: 8px; }
        .input-group { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
        input { width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #333; background: rgba(0,0,0,0.3); color: white; outline: none; }
        .btn { padding: 12px; border-radius: 10px; border: none; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; display: flex; align-items: center; justify-content[...]
        .btn-primary { background: linear-gradient(45deg, #00ffff, #7000ff); color: #000; }
        .btn-logout { background: #ff4757; color: white; padding: 8px 15px; }
        .user-item { background: rgba(255,255,255,0.03); border-radius: 12px; padding: 15px; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.05); }
        .user-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .username { font-weight: bold; color: var(--accent); font-size: 16px; }
        .project-tags { display: flex; flex-wrap: wrap; gap: 5px; margin: 10px 0; }
        .project-tag { background: rgba(0,255,255,0.1); color: var(--accent); padding: 4px 10px; border-radius: 6px; font-size: 11px; border: 1px solid rgba(0,255,255,0.2); }
        .action-row { display: flex; gap: 10px; margin-top: 10px; }
        .action-row form { flex: 2; }
        .action-row .btn-login { flex: 1; background: #fff; color: #000; font-size: 12px; }
    </style>
</head>
<body>
    <div class="bg-layer"><div class="orb orb-1"></div><div class="orb orb-2"></div><div style="position:absolute; width:100%; height:100%; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rg[...]
    <div class="header"><h2><i class="fa-solid fa-shield-halved"></i> ROOT</h2><a href="/logout" class="btn btn-logout"><i class="fa-solid fa-power-off"></i></a></div>
    <div class="stats-grid"><div class="stat-card"><i class="fa-solid fa-users"></i><p>Users</p><div>{{ users|length }}</div></div><div class="stat-card"><i class="fa-solid fa-rocket"></i><p>Acti[...]
    <div class="card"><h3><i class="fa-solid fa-gears"></i> Default Password</h3><form action="/admin/global_pw" method="post" class="input-group"><input type="text" name="global_pw" value="{{ gl[...]
    <div class="card"><h3><i class="fa-solid fa-user-gear"></i> User Management</h3>
        {% for u_name, u_pw in users.items() %}
        <div class="user-item"><div class="user-info"><span class="username"><i class="fa-solid fa-circle-user"></i> {{ u_name }}</span></div><div class="project-tags">
                {% set count = namespace(value=0) %}
                {% for p_key in start_times.keys() %}{% if p_key.startswith(u_name + '_') %}<span class="project-tag">● {{ p_key.split('_', 1)[1] }}</span>{% set count.value = count.value + 1 %[...]
                {% if count.value == 0 %}<span style="color:#666; font-size:11px;">No active bots</span>{% endif %}
            </div><div class="action-row"><form action="/admin/change_pw" method="post" style="display:flex; gap:5px;"><input type="hidden" name="username" value="{{ u_name }}"><input type="text"[...]
        {% endfor %}
    </div>
</body>
</html>
'''

# --- API & ROUTES ---

@app.route("/list_files/<name>")
def list_files(name):
    if 'username' not in session: return jsonify({"files": []})
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['username'])
    extract_dir = os.path.join(user_dir, name, "extracted")
    
    if not is_safe_path(user_dir, extract_dir):
        return jsonify({"files": [], "error": "Unauthorized path access"}), 403
        
    files = []
    if os.path.exists(extract_dir):
        for root, _, filenames in os.walk(extract_dir):
            for f in filenames:
                rel_path = os.path.relpath(os.path.join(root, f), extract_dir)
                files.append(rel_path)
    return jsonify({"files": files})

@app.route("/read_file", methods=["POST"])
def read_content():
    if 'username' not in session: return jsonify({"content": ""})
    data = request.json
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['username'])
    path = os.path.join(user_dir, data['project'], "extracted", data['filename'])
    
    if not is_safe_path(user_dir, path):
        return jsonify({"content": "Access Denied: Path Malformed"}), 403
        
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return jsonify({"content": f.read()})
    return jsonify({"content": ""})

@app.route("/save_file", methods=["POST"])
def save_content():
    if 'username' not in session: return jsonify({"status": "failed"})
    data = request.json
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['username'])
    path = os.path.join(user_dir, data['project'], "extracted", data['filename'])
    
    if not is_safe_path(user_dir, path):
        return jsonify({"status": "failed", "error": "Access Denied"}), 403
        
    with open(path, "w", encoding="utf-8") as f:
        f.write(data['content'])
    return jsonify({"status": "success"})

@app.route("/delete_file", methods=["POST"])
def delete_file_api():
    if 'username' not in session: return jsonify({"status": "failed"})
    data = request.json
    
    user_dir = os.path.join(UPLOAD_FOLDER, session['username'])
    path = os.path.join(user_dir, data['project'], "extracted", data['filename'])
    
    if not is_safe_path(user_dir, path):
        return jsonify({"status": "failed", "error": "Access Denied"}), 403
        
    if os.path.exists(path): os.remove(path)
    return jsonify({"status": "deleted"})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        l_type = request.form.get("login_type")
        username = request.form.get("username", "").strip()
        pw = request.form.get("password", "").strip()
        db = load_db()
        if l_type == "admin":
            if username == "admin" and pw == ADMIN_PASS:
                session['is_admin'], session['username'] = True, "admin"
                return redirect(url_for("admin_panel"))
        else:
            if username and username not in db["users"] and username != "admin":
                db["users"][username] = db["user_pw"]
                save_db(db)
            if username and pw == db["users"].get(username):
                session['is_admin'], session['username'] = False, username
                return redirect(url_for("index"))
    return render_template_string(LOGIN_HTML)

@app.route("/")
def index():
    if 'username' not in session: return redirect(url_for("login"))
    user_name = session['username']
    user_dir = os.path.join(UPLOAD_FOLDER, user_name)
    os.makedirs(user_dir, exist_ok=True)
    apps_list = []
    for name in os.listdir(user_dir):
        if os.path.isdir(os.path.join(user_dir, name)):
            p = processes.get((user_name, name))
            apps_list.append({"name": name, "running": (p is not None and p.poll() is None)})
    return render_template("index.html", apps=apps_list, username=user_name)

@app.route("/admin")
def admin_panel():
    if not session.get('is_admin'): return redirect(url_for("login"))
    db = load_db()
    return render_template_string(ADMIN_HTML, users=db["users"], start_times=db["start_times"], global_pw=db["user_pw"])

@app.route("/admin/global_pw", methods=["POST"])
def global_pw():
    if not session.get('is_admin'): return redirect(url_for("login"))
    db = load_db()
    db["user_pw"] = request.form.get("global_pw")
    save_db(db)
    return redirect(url_for("admin_panel"))

@app.route("/admin/change_pw", methods=["POST"])
def change_pw():
    if not session.get('is_admin'): return redirect(url_for("login"))
    u_name, new_pw = request.form.get("username"), request.form.get("new_pw")
    db = load_db()
    if u_name in db["users"]:
        db["users"][u_name] = new_pw
        save_db(db)
    return redirect(url_for("admin_panel"))

@app.route("/admin/login_as/<username>")
def login_as(username):
    if not session.get('is_admin'): return redirect(url_for("login"))
    session['username'], session['is_admin'] = username, False
    return redirect(url_for("index"))

# =================== MULTI-FILE SUPPORT RUN ROUTE ===================
@app.route("/run/<name>")
def run(name):
    if 'username' not in session: return redirect(url_for("login"))
    user_name = session['username']
    
    user_dir = os.path.abspath(os.path.join(UPLOAD_FOLDER, user_name))
    app_dir = os.path.abspath(os.path.join(user_dir, name))
    extract_dir = os.path.abspath(os.path.join(app_dir, "extracted"))
    
    if not is_safe_path(user_dir, app_dir):
        return redirect(url_for("index"))
        
    log_path = os.path.join(app_dir, "logs.txt")
    
    if (user_name, name) in file_handles:
        try: file_handles[(user_name, name)].close()
        except: pass
        
    if (user_name, name) not in processes or processes[(user_name, name)].poll() is not None:
        if not os.path.exists(extract_dir):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"[PANEL ERROR] Extracted directory does not exist: {extract_dir}\n")
            return redirect(url_for("index"))

        available_files = os.listdir(extract_dir)
        
        # main.py, app.py, bot.py ফাইলগুলোকে প্রায়োরিটি দিয়ে খোঁজা হচ্ছে
        main_file = next((f for f in ["main.py", "app.py", "bot.py", "index.js", "server.js"] if f in available_files), None)
        
        if main_file:
            log_file = open(log_path, "w", encoding="utf-8")
            file_handles[(user_name, name)] = log_file
            
            if main_file.endswith('.py'):
                cmd = ["python", "-u", main_file] # Unbuffered output fixed
            else:
                cmd = ["node", main_file]
                
            try:
                kwargs = {}
                if os.name != 'nt':
                    kwargs['preexec_fn'] = os.setsid
                    
                processes[(user_name, name)] = subprocess.Popen(
                    cmd, 
                    cwd=extract_dir, 
                    stdout=log_file, 
                    stderr=log_file, 
                    text=True,
                    **kwargs
                )
                
                # লগে ইউজারকে জানান কোন ফাইল দিয়ে বট চালু হলো
                log_file.write(f"[PANEL INFO] Starting your project using: {main_file}\n\n")
                log_file.flush()
                
                db = load_db()
                db["start_times"][f"{user_name}_{name}"] = int(time.time() * 1000)
                save_db(db)
                
            except Exception as e:
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"[PANEL ERROR] Failed to start process: {str(e)}\n")
        else:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("[PANEL ERROR] No startup file found!\n")
                f.write(f"Available files inside zip: {str(available_files)}\n")
                f.write("Please ensure your project has main.py, app.py, or bot.py directly in the root zip.\n")
                
    return redirect(url_for("index"))

@app.route("/get_log/<name>")
def get_log(name):
    user_name = session.get('username')
    if not user_name: return jsonify({"log": "", "status": "OFFLINE", "start_time": 0})
    
    user_dir = os.path.join(UPLOAD_FOLDER, user_name)
    app_dir = os.path.join(user_dir, name)
    
    if not is_safe_path(user_dir, app_dir):
        return jsonify({"log": "Access Denied", "status": "STOPPED", "start_time": 0}), 403
        
    log_path = os.path.join(app_dir, "logs.txt")
    log_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f: 
            log_content = f.read()[-2000:]
            
    p = processes.get((user_name, name))
    is_running = (p is not None and p.poll() is None)
    
    db = load_db()
    return jsonify({
        "log": log_content if log_content.strip() else "Waiting for logs...", 
        "status": "RUNNING" if is_running else "STOPPED", 
        "start_time": db["start_times"].get(f"{user_name}_{name}", 0)
    })

@app.route("/stop/<name>")
def stop(name):
    user_name = session.get('username')
    if not user_name: return redirect(url_for("login"))
    
    p = processes.pop((user_name, name), None)
    if p: 
        try:
            if os.name == 'nt':
                subprocess.Popen(f"taskkill /F /T /PID {p.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except:
            try: p.terminate()
            except: pass
            
    log_file = file_handles.pop((user_name, name), None)
    if log_file:
        try: log_file.close()
        except: pass
            
    db = load_db()
    if f"{user_name}_{name}" in db["start_times"]:
        del db["start_times"][f"{user_name}_{name}"]
        save_db(db)
    return redirect(url_for("index"))

@app.route("/upload", methods=["POST"])
def upload():
    if 'username' not in session: return redirect(url_for("login"))
    user_name = session['username']
    file = request.files.get("file")
    if file and file.filename.endswith(".zip"):
        app_name = file.filename.rsplit('.', 1)[0]
        user_dir = os.path.join(UPLOAD_FOLDER, user_name)
        app_dir = os.path.join(user_dir, app_name)
        
        if not is_safe_path(user_dir, app_dir):
            return redirect(url_for("index"))
            
        os.makedirs(app_dir, exist_ok=True)
        zip_path = os.path.join(app_dir, file.filename)
        file.save(zip_path)
        extract_dir = os.path.join(app_dir, "extracted")
        
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        os.remove(zip_path)
    return redirect(url_for("index"))

@app.route("/download/<name>")
def download(name):
    if 'username' not in session: return redirect(url_for("login"))
    user_name = session.get('username')
    
    user_dir = os.path.join(UPLOAD_FOLDER, user_name)
    app_dir = os.path.join(user_dir, name, "extracted")
    
    if not is_safe_path(user_dir, app_dir):
        return redirect(url_for("index"))
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zf.write(file_path, os.path.relpath(file_path, app_dir))
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"{name}.zip", as_attachment=True)

@app.route("/restart/<name>")
def restart(name):
    stop(name)
    time.sleep(1)
    return run(name)

@app.route("/delete/<name>")
def delete(name):
    user_name = session.get('username')
    if not user_name: return redirect(url_for("login"))
    stop(name)
    
    user_dir = os.path.join(UPLOAD_FOLDER, user_name)
    app_dir = os.path.join(user_dir, name)
    
    if not is_safe_path(user_dir, app_dir):
        return redirect(url_for("index"))
        
    if os.path.exists(app_dir): shutil.rmtree(app_dir)
    return redirect(url_for("index"))

@app.route("/logout")
def logout(): 
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3522, debug=False)
