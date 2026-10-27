"""
app2_proxy.py - reverse proxy for a Flask app.

Forwards  /app2/...  ->  http://127.0.0.1:8080/...
(method, headers, body and query string, using the requests library)

Use it in your platform's app.py, right after  app = Flask(__name__):

    from app2_proxy import register_app2_proxy
    register_app2_proxy(app)

Needs:  pip install requests   (add `requests` to requirements.txt)
Other target or prefix:  register_app2_proxy(app, target="http://127.0.0.1:5000", prefix="/panel")
"""
import re
from urllib.parse import quote

import requests
from flask import Response, request

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailers", "transfer-encoding", "upgrade"}


def register_app2_proxy(app, target="http://127.0.0.1:8080", prefix="/app2"):
    target = target.rstrip("/")
    prefix = "/" + prefix.strip("/")
    # Never hand the platform's own login cookie to the proxied app.
    own_cookie = app.config.get("SESSION_COOKIE_NAME", "session") + "="

    def reply(msg, status):
        return Response(msg, status=status, mimetype="text/plain")

    def rewrite_location(loc):
        """Keep redirects from the proxied app inside the prefix."""
        if loc.startswith(target):
            loc = loc[len(target):] or "/"
        elif not (loc.startswith("/") and not loc.startswith("//")):
            return loc
        if loc == prefix or loc.startswith(prefix + "/"):
            return loc                      # app already knows about the prefix
        return prefix + loc

    def proxy(path=""):
        url = f"{target}/{quote(path, safe='/')}"
        if request.query_string:
            url += "?" + request.query_string.decode("latin-1")

        skip = HOP_BY_HOP | {"host", "content-length", "cookie"}
        headers = {k: v for k, v in request.headers if k.lower() not in skip}
        cookie = "; ".join(c for c in request.headers.get("Cookie", "").split("; ")
                           if c and not c.startswith(own_cookie))
        if cookie:
            headers["Cookie"] = cookie
        prev = request.headers.get("X-Forwarded-For")
        headers["X-Forwarded-For"] = f"{prev}, {request.remote_addr}" if prev else request.remote_addr
        headers["X-Forwarded-Host"] = request.host
        headers["X-Forwarded-Proto"] = request.headers.get("X-Forwarded-Proto", request.scheme)
        headers["X-Forwarded-Prefix"] = prefix

        try:
            up = requests.request(request.method, url, headers=headers, data=request.get_data(),
                                  allow_redirects=False, stream=True, timeout=(5, 300))
        except requests.exceptions.ConnectionError:
            return reply(f"Cannot reach the app at {target}. Is it running?", 502)
        except requests.exceptions.Timeout:
            return reply("The app took too long to answer.", 504)

        out = []
        for k, v in up.raw.headers.items():
            kl = k.lower()
            if kl in HOP_BY_HOP or kl == "set-cookie":
                continue
            out.append((k, rewrite_location(v) if kl == "location" else v))
        for c in up.raw.headers.getlist("Set-Cookie"):    # keep every cookie, scope it to the prefix
            out.append(("Set-Cookie",
                        re.sub(r"(?i)(;\s*path=)(/[^;]*)",
                               lambda m: m.group(1) + prefix + m.group(2), c)))

        def body():
            try:
                yield from up.raw.stream(8192, decode_content=False)   # bytes exactly as sent
            finally:
                up.close()

        return Response(body(), status=up.status_code, headers=out)

    app.add_url_rule(prefix + "/", endpoint="app2_proxy_root", view_func=proxy,
                     defaults={"path": ""}, methods=METHODS, provide_automatic_options=False)
    app.add_url_rule(prefix + "/<path:path>", endpoint="app2_proxy", view_func=proxy,
                     methods=METHODS, provide_automatic_options=False)
