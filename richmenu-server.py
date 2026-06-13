#!/usr/bin/env python3
import json, os, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

NB_HOST = os.environ.get("NB_HOST", "127.0.0.1")
NB = "http://%s:8080/api/v3/data/p9zwkc6ert3qwko/mcspxjoby42vevi/records?pageSize=1" % NB_HOST
XC = os.environ.get("XC", "")
CELLS = [(0,0,833,843),(833,0,834,843),(1667,0,833,843),
         (0,843,833,843),(833,843,834,843),(1667,843,833,843)]

def http(method, url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def get_settings():
    s, body = http("GET", NB, {"xc-token": XC})
    f = json.loads(body)["records"][0]["fields"]
    token = (f.get("channel_access_token") or "").replace("Bearer ", "").strip()
    cfg = json.loads(f.get("richmenu_json") or "{}")
    return token, cfg

def build_areas(buttons):
    areas = []
    for i, b in enumerate(buttons[:6]):
        t = b.get("type"); v = (b.get("value") or "").strip()
        if not t or not v: continue
        x,y,w,h = CELLS[i]
        if t == "card":   action = {"type":"postback","data":"action="+v}
        elif t == "uri":  action = {"type":"uri","uri":v}
        elif t == "text": action = {"type":"message","text":v}
        else: continue
        areas.append({"bounds":{"x":x,"y":y,"width":w,"height":h},"action":action})
    return areas

def apply():
    token, cfg = get_settings()
    if not token: return {"ok":False,"error":"找不到 LINE token"}
    image = (cfg.get("image") or "").strip()
    areas = build_areas(cfg.get("buttons", []))
    if not image: return {"ok":False,"error":"未設定選單圖片"}
    if not areas: return {"ok":False,"error":"沒有任何按鈕設定動作"}
    H = {"Authorization":"Bearer "+token, "Content-Type":"application/json"}
    rm = {"size":{"width":2500,"height":1686},"selected":True,
          "name":"CHARGESPOT 商戶選單","chatBarText":"商戶服務選單","areas":areas}
    s, body = http("POST","https://api.line.me/v2/bot/richmenu", H, json.dumps(rm).encode())
    if s != 200: return {"ok":False,"step":"建立選單","code":s,"resp":body.decode("utf-8","replace")}
    rmid = json.loads(body)["richMenuId"]
    si, img = http("GET", image, {"xc-token": XC})
    if si != 200 or not img: si, img = http("GET", image)
    if si != 200: return {"ok":False,"step":"抓圖片","code":si}
    ctype = "image/png" if image.lower().split("?")[0].endswith(".png") else "image/jpeg"
    s, body = http("POST", "https://api-data.line.me/v2/bot/richmenu/%s/content"%rmid,
                   {"Authorization":"Bearer "+token,"Content-Type":ctype}, img)
    if s != 200: return {"ok":False,"step":"上傳圖片","code":s,"resp":body.decode("utf-8","replace")}
    s, body = http("POST", "https://api.line.me/v2/bot/user/all/richmenu/%s"%rmid,
                   {"Authorization":"Bearer "+token,"Content-Length":"0"}, b"")
    if s != 200: return {"ok":False,"step":"設為預設","code":s,"resp":body.decode("utf-8","replace")}
    s, body = http("GET","https://api.line.me/v2/bot/richmenu/list",{"Authorization":"Bearer "+token})
    deleted = 0
    if s == 200:
        for m in json.loads(body).get("richmenus", []):
            if m["richMenuId"] != rmid:
                http("DELETE","https://api.line.me/v2/bot/richmenu/%s"%m["richMenuId"],{"Authorization":"Bearer "+token})
                deleted += 1
    return {"ok":True,"richMenuId":rmid,"按鈕數":len(areas),"清除舊選單":deleted}

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_GET(self):
        self.send_response(200); self._cors()
        self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(b'{"status":"richmenu-apply ready"}')
    def do_POST(self):
        try: result = apply()
        except Exception as e: result = {"ok":False,"error":str(e)}
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200 if result.get("ok") else 500); self._cors()
        self.send_header("Content-Type","application/json; charset=utf-8"); self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a): pass

if __name__ == "__main__":
    if os.environ.get("RUN_ONCE"):
        print(json.dumps(apply(), ensure_ascii=False))
    else:
        HTTPServer(("0.0.0.0",5690), Handler).serve_forever()
