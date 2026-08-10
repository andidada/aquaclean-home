#!/usr/bin/env python3
"""
AquaClean Dashboard GitHub Bridge
Listens on localhost:18765, exposes:
  GET /token         -> returns GitHub PAT (no body, just text)
  POST /commit       -> body JSON {files:{path:content}, message}
                       -> commits to andida/aquaclean-home main
                       -> returns {ok, sha, url, netlify_url}
                       -> triggers GitHub Actions redeploy
"""
import http.server, json, threading, urllib.request, urllib.error, base64, ctypes, struct, os, sys

PORT = 18765
REPO = "andidada/aquaclean-home"
BASE = "https://api.github.com"

# ── Read PAT from Windows Credential Manager ────────────────────────────────
def get_pat():
    CredRead = ctypes.windll.advapi32.CredReadW
    CredRead.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                          ctypes.POINTER(ctypes.c_void_p)]
    CredRead.restype = ctypes.c_bool
    CredFree = ctypes.windll.advapi32.CredFree
    CredFree.argtypes = [ctypes.c_void_p]
    p = ctypes.c_void_p()
    ok = CredRead("git:https://github.com", 1, 0, ctypes.byref(p))
    if not ok:
        raise RuntimeError("Could not read GitHub credential from Windows Credential Manager")
    base = p.value
    blob_size = struct.unpack("<I", ctypes.string_at(base + 32, 4))[0]
    blob_ptr  = struct.unpack("<Q", ctypes.string_at(base + 40, 8))[0]
    pat = ctypes.wstring_at(blob_ptr, blob_size // 2).strip()
    CredFree(p.value)
    return pat

def api(method, path, data=None, token=None):
    """Make GitHub API request. data=None -> GET, else POST/PATCH."""
    url = BASE + path
    h = {
        "Authorization": f"Bearer {token or PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = json.dumps(data).encode() if data is not None else None
    if body:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return (r.status, json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return (e.code, {"error": e.read().decode(errors="replace")[:200]})

PAT = None  # lazily loaded

# ── Get current main commit SHA ──────────────────────────────────────────────
def get_main_info():
    _, ref = api("GET", f"/repos/{REPO}/git/ref/heads/main", token=PAT)
    commit_sha = ref["object"]["sha"]
    _, commit  = api("GET", f"/repos/{REPO}/git/commits/{commit_sha}", token=PAT)
    return commit_sha, commit["tree"]["sha"]

# ── Create blob ──────────────────────────────────────────────────────────────
def create_blob(content, path_hint):
    is_binary = isinstance(content, bytes)
    encoded = base64.b64encode(content).decode() if is_binary else content
    _, blob = api("POST", f"/repos/{REPO}/git/blobs",
                  {"content": encoded,
                   "encoding": "base64" if is_binary else "utf-8"},
                  token=PAT)
    return blob["sha"]

# ── Build new tree ───────────────────────────────────────────────────────────
def build_tree(root_sha, file_changes):
    """
    file_changes: list of (path, sha_or_content, is_binary)
    Returns new tree SHA.
    """
    # Fetch current root tree
    _, rt = api("GET", f"/repos/{REPO}/git/trees/{root_sha}", token=PAT)
    entries = {e["path"]: e for e in rt["tree"]}

    # Create blobs for changed files and collect new tree entries
    new_entries = []
    for path, content, is_binary in file_changes:
        if content.startswith("blob:"):
            sha = content[5:]
        else:
            sha = create_blob(content.encode("utf-8") if not is_binary else content, path)
        new_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
        if path in entries:
            del entries[path]

    # Remaining unchanged entries
    for path, e in entries.items():
        new_entries.append({"path": path, "mode": e["mode"],
                            "type": e["type"], "sha": e["sha"]})

    _, tree = api("POST", f"/repos/{REPO}/git/trees",
                   {"tree": new_entries, "base_tree": root_sha}, token=PAT)
    return tree["sha"]

# ── Commit ───────────────────────────────────────────────────────────────────
def create_commit(tree_sha, parent_sha, message):
    _, commit = api("POST", f"/repos/{REPO}/git/commits",
                    {"message": message, "tree": tree_sha, "parents": [parent_sha]},
                    token=PAT)
    return commit["sha"]

# ── Update ref ───────────────────────────────────────────────────────────────
def update_ref(new_sha):
    api("PATCH", f"/repos/{REPO}/git/refs/heads/main",
        {"sha": new_sha, "force": True}, token=PAT)

# ── Trigger GitHub Actions ────────────────────────────────────────────────────
def trigger_actions():
    # Get workflow ID
    _, wfs = api("GET", f"/repos/{REPO}/actions/workflows", token=PAT)
    wf_id = None
    for wf in wfs.get("workflows", []):
        if wf.get("name") == "Deploy to Netlify":
            wf_id = wf["id"]
            break
    if wf_id:
        api("POST", f"/repos/{REPO}/actions/workflows/{wf_id}/dispatches",
            {"ref": "main"}, token=PAT)
    return wf_id

# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        global PAT
        if self.path == "/token":
            if not PAT:
                PAT = get_pat()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(PAT.encode())
        elif self.path == "/status":
            try:
                if not PAT:
                    PAT = get_pat()
                self.send_json(200, {"status": "ok", "repo": REPO})
            except Exception as e:
                self.send_json(200, {"status": "error", "msg": str(e)})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        global PAT
        if self.path != "/commit":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            if not PAT:
                PAT = get_pat()

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)

            files  = payload.get("files", {})   # {path: content_string}
            msg    = payload.get("message", "Update content via dashboard")
            bump   = payload.get("bump_version", True)

            print(f"Commit request: {len(files)} files, msg='{msg}'")

            # Get current main tip
            parent_sha, root_sha = get_main_info()

            # Build file list
            file_changes = []
            for path, content in files.items():
                file_changes.append((path, content, False))

            # Optionally bump version string in HTML files
            if bump:
                import hashlib, time
                short_sha = hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
                new_ver   = f"?v={short_sha}"
                # Bump ?v= in all HTML files in the commit
                for path in list(files.keys()):
                    if path.endswith(".html") and new_ver not in files[path]:
                        # Replace existing ?v= pattern
                        import re
                        files[path] = re.sub(r'\?v=[a-z0-9]+', new_ver, files[path])
                        file_changes = [(p, c, False) for p, c in files.items()]

            # Build new tree
            new_tree_sha = build_tree(root_sha, file_changes)

            # Create commit
            new_commit_sha = create_commit(new_tree_sha, parent_sha, msg)

            # Update main ref
            update_ref(new_commit_sha)

            # Trigger GitHub Actions
            wf_id = trigger_actions()

            result = {
                "ok": True,
                "commit_sha": new_commit_sha,
                "commit_url": f"https://github.com/{REPO}/commit/{new_commit_sha}",
                "actions_triggered": bool(wf_id),
            }
            print(f"Commit {new_commit_sha} pushed successfully")
            self.send_json(200, result)

        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json(500, {"ok": False, "error": str(e)})

server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
print(f"AquaClean GitHub Bridge running on http://127.0.0.1:{PORT}")
print("Endpoints:")
print(f"  GET  /token     -> GitHub PAT")
print(f"  GET  /status    -> check if token readable")
print(f"  POST /commit    -> commit files to {REPO}")
print("PID:", os.getpid())
server.serve_forever()
