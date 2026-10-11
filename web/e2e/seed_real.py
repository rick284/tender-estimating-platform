import json, urllib.request, uuid
def call(method, path, body=None, files=None, form=None, tok=None):
    url = "http://localhost:8000" + path; h = {}
    if tok: h["Authorization"] = f"Bearer {tok}"
    if files:
        bd = uuid.uuid4().hex; parts = []
        for k, v in (form or {}).items(): parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, (fn, data) in files.items(): parts.append(f'--{bd}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
        parts.append(f"--{bd}--\r\n".encode()); data = b"".join(parts); h["Content-Type"] = f"multipart/form-data; boundary={bd}"
    else: data = json.dumps(body).encode() if body is not None else None; h["Content-Type"] = "application/json"
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h)))
r = call("POST", "/api/auth/register", {"email": "rick@3bearsprojects.co.nz", "password": "a long test password", "name": "Rick", "company": "3Bears Projects"})
tok = r["token"]
for f in ("Rev34C", "Rev34E"):
    data = open(f"/home/user/tender-estimating-platform/private/{f}.xlsx", "rb").read()
    if f == "Rev34C": t = call("POST", "/api/tenders", files={"file": (f"{f}.xlsx", data)}, form={"client": "Siteworks (TPW)"}, tok=tok)
    else: call("POST", f"/api/tenders/{t['id']}/revisions", files={"file": (f"{f}.xlsx", data)}, tok=tok)
print("seeded", t["name"])
