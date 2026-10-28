"""
Pyhost - a small hosting panel built with Flask.
Upload a .py or .zip project, then start, stop and watch its logs from the browser.

Run:
    pip install flask
    HOST_PASSWORD=your-password python hosting_server.py      (Linux / Termux)
Then open http://<your-ip>:8080
"""
import os
import re
import sys
import shutil
import atexit
import socket
import secrets
import zipfile
import subprocess
from functools import wraps
from pathlib import Path

from flask import (Flask, request, session, redirect, flash, abort,
                   render_template_string, Response)
from urllib.parse import quote, urlsplit
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

try:
    import requests
except ImportError:  # pip install requests
    requests = None

BASE = Path(__file__).parent.resolve()
# Everything that must survive a redeploy lives in DATA (a Railway volume if one is attached).
DATA = Path(os.environ.get("DATA_DIR") or os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or BASE).resolve()
PROJECTS = DATA / "projects"
PROJECTS.mkdir(parents=True, exist_ok=True)
LIBS = DATA / ".pylibs"   # packages installed from the panel, used by every project

# A host platform built on Flask can leak these into us and make Werkzeug
# think it is a reloader child (Errno 9 Bad file descriptor), so drop them.
for _k in ("WERKZEUG_RUN_MAIN", "WERKZEUG_SERVER_FD"):
    os.environ.pop(_k, None)


def load_password():
    if os.environ.get("HOST_PASSWORD"):
        return os.environ["HOST_PASSWORD"], False
    f = DATA / ".panel_password"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(9))
    return f.read_text().strip(), True


PASSWORD, GENERATED = load_password()
PORT = int(os.environ.get("PORT") or os.environ.get("SERVER_PORT") or 8080)

def load_secret():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    f = DATA / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_hex(24))
    return f.read_text().strip()


app = Flask(__name__)
app.secret_key = load_secret()
app.config.update(MAX_CONTENT_LENGTH=200 * 1024 * 1024,
                  SESSION_COOKIE_NAME="pyhost_session",
                  SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_HTTPONLY=True)

app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)   # lets the panel live under /app2/ behind a proxy


@app.context_processor
def inject_root():
    return {"root": request.script_root}


def go(path):
    return redirect(request.script_root + path)


procs = {}   # project name -> Popen
ports = {}   # project name -> port passed to the project as $PORT


# ---------- helpers ----------
def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("ok"):
            return go("/login")
        return fn(*a, **kw)
    return wrapper


def pdir(name):
    safe = secure_filename(name)
    d = PROJECTS / safe
    if not safe or not d.is_dir():
        abort(404)
    return d


def py_files(d):
    return sorted(f.name for f in d.glob("*.py"))


def get_entry(d):
    saved = d / ".entry"
    if saved.exists():
        n = saved.read_text().strip()
        if (d / n).is_file():
            return n
    for n in ("main.py", "app.py", "bot.py", "run.py", "server.py"):
        if (d / n).is_file():
            return n
    files = py_files(d)
    return files[0] if files else None


def is_running(name):
    p = procs.get(name)
    return p is not None and p.poll() is None


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start(name):
    d = pdir(name)
    entry = get_entry(d)
    if not entry:
        flash("No .py file found in this project.")
        return
    if is_running(name):
        return
    ports[name] = free_port()
    env = {**os.environ, "PORT": str(ports[name]), "PYTHONUNBUFFERED": "1",
           "PYTHONPATH": os.pathsep.join(filter(None, [str(LIBS), os.environ.get("PYTHONPATH")]))}
    log = open(d / "run.log", "ab")
    procs[name] = subprocess.Popen([sys.executable, "-u", entry], cwd=d,
                                   stdout=log, stderr=subprocess.STDOUT, env=env)


def stop(name):
    p = procs.get(name)
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")   # terminal colour codes


def tail(path, n=20000):
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - n))
        return ANSI_RE.sub("", f.read().decode("utf-8", "replace"))


def safe_extract(zf, dest):
    root = str(dest.resolve()) + os.sep
    for m in zf.infolist():
        if not str((dest / m.filename).resolve()).startswith(root):
            raise ValueError("Unsafe path in zip")
    zf.extractall(dest)


def pip_install(d, args):
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(LIBS),
                            "--upgrade", *args], cwd=d,
                           capture_output=True, text=True, timeout=900)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        out = "pip install took too long and was stopped."
    with open(d / "run.log", "a", encoding="utf-8") as lf:
        lf.write("\n--- pip install " + " ".join(args) + " ---\n" + out + "\n")


def lan_ips():
    found = []
    for cmd in (["ip", "-4", "-o", "addr"], ["ifconfig"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
        except Exception:
            continue
        for ip in re.findall(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", out):
            if re.match(r"(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))", ip) and ip not in found:
                found.append(ip)
        if found:
            break
    return found


# ---------- pages ----------
CSS = """
:root{--bg:#13161b;--panel:#1b1f26;--line:#2b313b;--tx:#e8eaee;--mut:#8f97a6;--ok:#3ccf91;--bad:#ef6a6a;--ac:#6ea8ff}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
padding:env(safe-area-inset-top) 0 calc(32px + env(safe-area-inset-bottom))}
.wrap{max-width:720px;margin:0 auto;padding:16px}
a{color:var(--ac);text-decoration:none}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
h1{font-size:1.5rem;margin:.6rem 0 1rem}
.top{display:flex;justify-content:space-between;align-items:center;padding-bottom:12px;border-bottom:1px solid var(--line)}
.top b{font-size:1.05rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:16px}
label{display:block;margin-bottom:10px;color:var(--mut);font-size:.9rem}
input,select{width:100%;margin-top:4px;padding:10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--tx);font:inherit}
button{padding:10px 16px;border:0;border-radius:8px;background:var(--ac);color:#0b1220;font:inherit;font-weight:600;cursor:pointer}
button.alt{background:var(--line);color:var(--tx)}
button.danger{background:var(--bad);color:#2a0b0b}
.row{display:flex;align-items:center;gap:12px;padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;margin-bottom:10px;color:var(--tx)}
.row small{margin-left:auto;color:var(--mut)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--mut);flex:none}
.dot.on{background:var(--ok)}
.mut{color:var(--mut)}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.btns form{margin:0}
.msg{background:#2a2414;border:1px solid #5a4a1a;padding:10px 12px;border-radius:8px;margin:12px 0}
pre{background:#0d0f13;border:1px solid var(--line);border-radius:10px;padding:12px;height:50vh;overflow:auto;
font:13px/1.45 ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-word}
"""

LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{{ title }} - Pyhost</title><style>{{ css|safe }}</style></head><body><div class="wrap">
{% if authed %}<div class="top"><b><a href="{{ root }}/" style="color:inherit">Pyhost</a></b><a href="{{ root }}/logout">Log out</a></div>{% endif %}
{% for m in get_flashed_messages() %}<div class="msg">{{ m }}</div>{% endfor %}
{{ body|safe }}
</div></body></html>"""


def page(title, body, **ctx):
    inner = render_template_string(body, **ctx)
    return render_template_string(LAYOUT, title=title, css=CSS, body=inner,
                                  authed=session.get("ok"))


LOGIN = """<h1>Log in</h1><form class="card" method="post">
<label>Password<input type="password" name="password" autofocus required></label>
<button>Log in</button></form>"""

HOME = """<h1>Projects</h1>
<form class="card" method="post" action="{{ root }}/upload" enctype="multipart/form-data">
<label>File (.py or .zip)<input type="file" name="file" accept=".py,.zip" required></label>
<label>Project name (optional)<input name="name" placeholder="my-bot"></label>
<button>Upload</button></form>
<form class="card" method="post" action="{{ root }}/_pyhost/web-port">
<label>Web dashboard port (the project's own page then opens at <a href="{{ root }}/app2/">/app2/</a>)
<input name="port" inputmode="numeric" placeholder="3050" value="{{ web_port or '' }}"></label>
<button class="alt">Save</button></form>
{% for p in projects %}
<a class="row" href="{{ root }}/p/{{ p.name }}"><span class="dot {{ 'on' if p.up }}"></span><b>{{ p.name }}</b>
<small>{{ 'Running' if p.up else 'Stopped' }}</small></a>
{% else %}<p class="mut">No projects yet. Upload a .py file or a .zip to start one.</p>{% endfor %}"""

DETAIL = """<p><a href="{{ root }}/">Back to projects</a></p>
<h1>{{ name }}</h1>
<p class="mut">{{ 'Running' if up else 'Stopped' }}{% if up %}, $PORT={{ port }}{% endif %}</p>
<form class="card" method="post" action="{{ root }}/p/{{ name }}/entry">
<label>File to run<select name="entry">{% for f in files %}
<option value="{{ f }}" {{ 'selected' if f == entry }}>{{ f }}</option>{% endfor %}</select></label>
<button class="alt">Save</button></form>
<div class="btns">
<form method="post" action="{{ root }}/p/{{ name }}/start"><button>Start</button></form>
<form method="post" action="{{ root }}/p/{{ name }}/stop"><button class="alt">Stop</button></form>
<form method="post" action="{{ root }}/p/{{ name }}/restart"><button class="alt">Restart</button></form>
{% if has_req %}<form method="post" action="{{ root }}/p/{{ name }}/install"><button class="alt">Install requirements</button></form>{% endif %}
<form method="post" action="{{ root }}/p/{{ name }}/autostart"><button class="alt">Auto-start: {{ 'on' if auto else 'off' }}</button></form>
<form method="post" action="{{ root }}/p/{{ name }}/delete" onsubmit="return confirm('Delete {{ name }} and all its files?')">
<button class="danger">Delete</button></form></div>
<form class="card" method="post" action="{{ root }}/p/{{ name }}/pip">
<label>Install packages<input name="pkgs" placeholder="flask requests protobuf" autocapitalize="none" autocomplete="off"></label>
<button class="alt">pip install</button></form>
<pre id="log">{{ log }}</pre>
<script>
const el=document.getElementById('log');el.scrollTop=el.scrollHeight;
setInterval(async()=>{try{const r=await fetch('{{ root }}/p/{{ name }}/log');if(!r.ok)return;
const end=el.scrollHeight-el.scrollTop-el.clientHeight<40;el.textContent=await r.text();
if(end)el.scrollTop=el.scrollHeight}catch(e){}},3000);
</script>"""


# ---------- routes ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), PASSWORD):
            session["ok"] = True
            return go("/")
        flash("Wrong password.")
    return page("Log in", LOGIN)


@app.get("/logout")
def logout():
    session.clear()
    return go("/login")


@app.get("/")
@login_required
def home():
    projects = [{"name": d.name, "up": is_running(d.name)}
                for d in sorted(PROJECTS.iterdir()) if d.is_dir()]
    return page("Projects", HOME, projects=projects, web_port=web_port_saved())


@app.post("/upload")
@login_required
def upload():
    f = request.files.get("file")
    fname = secure_filename(f.filename) if f and f.filename else ""
    ext = Path(fname).suffix.lower()
    if ext not in (".py", ".zip"):
        flash("Upload a .py or .zip file.")
        return go("/")
    name = secure_filename(request.form.get("name") or "") or secure_filename(Path(fname).stem)
    if not name:
        flash("Give the project a name.")
        return go("/")
    d = PROJECTS / name
    d.mkdir(exist_ok=True)
    was_running = is_running(name)
    if was_running:
        stop(name)
    if ext == ".py":
        f.save(d / fname)
    else:
        tmp = d / "_extract"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        zpath = d / "_upload.zip"
        f.save(zpath)
        try:
            with zipfile.ZipFile(zpath) as z:
                safe_extract(z, tmp)
            items = [i for i in tmp.iterdir() if i.name != "__MACOSX"]
            src = items[0] if len(items) == 1 and items[0].is_dir() else tmp
            shutil.copytree(src, d, dirs_exist_ok=True)
        except (zipfile.BadZipFile, ValueError) as e:
            flash(f"Could not read the zip: {e}")
        finally:
            zpath.unlink(missing_ok=True)
            shutil.rmtree(tmp, ignore_errors=True)
    if was_running:
        start(name)
    return go(f"/p/{name}")


@app.get("/p/<name>")
@login_required
def detail(name):
    d = pdir(name)
    return page(name, DETAIL, name=d.name, up=is_running(d.name), port=ports.get(d.name),
               files=py_files(d), entry=get_entry(d), has_req=(d / "requirements.txt").is_file(),
               log=tail(d / "run.log"), auto=(d / ".autostart").exists())


@app.get("/p/<name>/log")
@login_required
def log(name):
    return Response(tail(pdir(name) / "run.log"), mimetype="text/plain")


@app.post("/p/<name>/<action>")
@login_required
def act(name, action):
    d = pdir(name)
    if action == "start":
        start(d.name)
    elif action == "stop":
        stop(d.name)
    elif action == "restart":
        stop(d.name)
        start(d.name)
    elif action == "entry":
        pick = request.form.get("entry", "")
        if pick in py_files(d):
            (d / ".entry").write_text(pick)
    elif action == "install":
        pip_install(d, ["-r", "requirements.txt"])
    elif action == "pip":
        pkgs = request.form.get("pkgs", "").split()
        ok = pkgs and all(re.match(r"^[A-Za-z0-9][A-Za-z0-9_.\-\[\]=<>~!,]*$", p) for p in pkgs)
        if ok:
            pip_install(d, pkgs)
        else:
            flash("Package names only, separated by spaces.")
    elif action == "autostart":
        flag = d / ".autostart"
        if flag.exists():
            flag.unlink()
        else:
            flag.touch()
    elif action == "delete":
        stop(d.name)
        procs.pop(d.name, None)
        shutil.rmtree(d, ignore_errors=True)
        return go("/")
    else:
        abort(404)
    return go(f"/p/{d.name}")


# ---------- reverse proxy: /app2/ (and unknown paths) -> the project's web dashboard ----------
APP2_PREFIX = "/app2"
PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailers", "transfer-encoding", "upgrade"}


def web_port_saved():
    f = DATA / ".app2_port"
    return f.read_text().strip() if f.exists() else ""


def app2_target():
    """(url, configured). Port comes from the home page box, else APP2_URL / APP2_PORT."""
    saved = web_port_saved()
    if saved.isdigit():
        return f"http://127.0.0.1:{saved}", True
    if os.environ.get("APP2_URL"):
        return os.environ["APP2_URL"].rstrip("/"), True
    if os.environ.get("APP2_PORT"):
        return f"http://127.0.0.1:{os.environ['APP2_PORT']}", True
    return "http://127.0.0.1:8080", False


def fallback_on():
    """Paths the panel does not know (/api/..., /static/...) go to the dashboard too."""
    return app2_target()[1] and os.environ.get("APP2_FALLBACK", "1") != "0"


def text_reply(msg, status):
    return Response(msg, status=status, mimetype="text/plain")


def rewrite_location(loc, target, prefix):
    """Keep redirects from the proxied app inside the prefix."""
    if loc.startswith(target):
        loc = loc[len(target):] or "/"
    elif not (loc.startswith("/") and not loc.startswith("//")):
        return loc
    if prefix and (loc == prefix or loc.startswith(prefix + "/")):
        return loc
    return prefix + loc


def gate():
    """The dashboard sits behind the panel login unless APP2_REQUIRE_LOGIN=0."""
    if os.environ.get("APP2_REQUIRE_LOGIN", "1") != "0" and not session.get("ok"):
        return go("/login")
    return None


def forward(path, prefix):
    if requests is None:
        return text_reply("The requests library is missing. Run: pip install requests", 503)
    target, _ = app2_target()
    t = urlsplit(target)
    if t.hostname in ("127.0.0.1", "localhost", "0.0.0.0") and t.port == PORT:
        return text_reply(f"The web port points at this panel itself (port {PORT}). "
                          "Set the dashboard's own port instead.", 508)

    url = f"{target}/{quote(path, safe='/')}"
    if request.query_string:
        url += "?" + request.query_string.decode("latin-1")

    # Forward the request headers, minus hop-by-hop ones and the panel's own cookie.
    skip = HOP_BY_HOP | {"host", "content-length", "cookie"}
    headers = {k: v for k, v in request.headers if k.lower() not in skip}
    own = app.config["SESSION_COOKIE_NAME"] + "="
    cookie = "; ".join(c for c in request.headers.get("Cookie", "").split("; ")
                       if c and not c.startswith(own))
    if cookie:
        headers["Cookie"] = cookie
    prev = request.headers.get("X-Forwarded-For")
    headers["X-Forwarded-For"] = f"{prev}, {request.remote_addr}" if prev else request.remote_addr
    headers["X-Forwarded-Host"] = request.host
    headers["X-Forwarded-Proto"] = request.headers.get("X-Forwarded-Proto", request.scheme)
    if prefix:
        headers["X-Forwarded-Prefix"] = prefix

    try:
        up = requests.request(request.method, url, headers=headers, data=request.get_data(),
                              allow_redirects=False, stream=True, timeout=(5, 300))
    except requests.exceptions.ConnectionError:
        return text_reply(f"Cannot reach the dashboard at {target}. Is the project running "
                          "and is the port right?", 502)
    except requests.exceptions.Timeout:
        return text_reply("The dashboard took too long to answer.", 504)

    out = []
    for k, v in up.raw.headers.items():
        kl = k.lower()
        if kl in HOP_BY_HOP or kl == "set-cookie":
            continue
        out.append((k, rewrite_location(v, target, prefix) if kl == "location" else v))
    scope = bool(prefix) and not fallback_on()   # with fallback on, cookies must stay on Path=/
    for c in up.raw.headers.getlist("Set-Cookie"):
        if scope:
            c = re.sub(r"(?i)(;\s*path=)(/[^;]*)", lambda m: m.group(1) + prefix + m.group(2), c)
        out.append(("Set-Cookie", c))

    def body():
        try:
            yield from up.raw.stream(8192, decode_content=False)   # bytes exactly as sent
        finally:
            up.close()

    return Response(body(), status=up.status_code, headers=out)


@app.route("/app2/", defaults={"path": ""}, methods=PROXY_METHODS,
           provide_automatic_options=False)
@app.route("/app2/<path:path>", methods=PROXY_METHODS, provide_automatic_options=False)
def app2_proxy(path):
    blocked = gate()
    return blocked if blocked is not None else forward(path, APP2_PREFIX)


@app.errorhandler(404)
def not_found(e):
    p = request.path
    if fallback_on() and not p.startswith(("/p/", "/app2", "/_pyhost")):
        blocked = gate()
        return blocked if blocked is not None else forward(p.lstrip("/"), "")
    return e


@app.post("/_pyhost/web-port")
@login_required
def set_web_port():
    f = DATA / ".app2_port"
    val = request.form.get("port", "").strip()
    if not val:
        f.unlink(missing_ok=True)
    elif val.isdigit() and 1 <= int(val) <= 65535 and int(val) != PORT:
        f.write_text(val)
    else:
        flash(f"Enter a port from 1 to 65535 (not {PORT}, that is the panel itself).")
    return go("/")


if __name__ == "__main__":
    if GENERATED:
        print(f"Panel password (HOST_PASSWORD not set): {PASSWORD}")
    atexit.register(lambda: [stop(n) for n in list(procs)])
    with app.test_request_context():
        for d in PROJECTS.iterdir():
            if d.is_dir() and (d / ".autostart").exists():
                start(d.name)
    print(f"Pyhost running. This phone:  http://127.0.0.1:{PORT}")
    for ip in lan_ips():
        print(f"On WiFi / hotspot:           http://{ip}:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
