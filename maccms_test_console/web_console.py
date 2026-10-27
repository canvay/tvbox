# coding=utf-8
# 资源站 / 解析接口 测试操作台 —— 后端（仅用 Python 标准库，零依赖）
# 启动：python web_console.py  然后浏览器打开 http://localhost:8000
import http.server, json, urllib.request, urllib.error, ssl, time, os, re
from urllib.parse import urlparse, urlencode

PORT = 8000
HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"


def do_request(url, method="GET", params=None, body=None, headers=None, timeout=12):
    """统一请求封装，返回结构化结果。"""
    t0 = time.time()
    if not url or not str(url).strip():
        return {"error": "URL 不能为空，请填写请求地址", "time_ms": 0}
    try:
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urlencode(params)
        req_headers = {"User-Agent": UA}
        if headers:
            req_headers.update(headers)
        data = None
        if method == "POST" and body is not None:
            if isinstance(body, str):
                data = body.encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")
            else:
                data = body
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.getcode()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        status = e.code
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:120]}", "time_ms": int((time.time()-t0)*1000)}

    ms = int((time.time() - t0) * 1000)
    text = ""
    try:
        text = raw.decode("utf-8", "replace")
    except Exception:
        text = repr(raw[:500])
    # 尝试 JSON 解析
    pretty = None
    ok = False
    try:
        obj = json.loads(text)
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
        ok = True
    except Exception:
        if "<list" in text or "<?xml" in text or "<rss" in text:
            ok = True  # XML 也视为合法响应
    return {
        "status": status, "time_ms": ms, "content_type": ctype,
        "ok": ok, "body": text, "pretty": pretty,
    }


def maccms(base, action, ids=None):
    base = base.rstrip("/")
    if action == "list":
        url = base + "/?ac=list&at=json"
    elif action == "videolist":
        url = base + "/?ac=videolist&at=json&pg=1"
    elif action == "detail":
        url = base + "/?ac=detail&at=json&ids=" + (ids or "")
    else:
        return {"error": "unknown action"}
    r = do_request(url, headers={"Referer": "https://www.baidu.com/"})
    if r.get("error"):
        return r
    try:
        obj = json.loads(r["body"])
    except Exception:
        return {"error": "返回非 JSON（可能需要带 at=json，或站点已改版/WAF 拦截）", "status": r.get("status")}
    if action == "list":
        types = obj.get("list") or obj.get("class") or []
        out = [{"type_id": str(t.get("type_id", "")), "type_name": t.get("type_name", "")} for t in types]
        return {"status": r["status"], "time_ms": r["time_ms"], "list": out}
    if action == "videolist":
        lst = obj.get("list") or []
        out = [{"vod_id": str(v.get("vod_id", "")), "vod_name": v.get("vod_name", ""),
                "vod_remarks": v.get("vod_remarks", "")} for v in lst]
        return {"status": r["status"], "time_ms": r["time_ms"], "total": obj.get("total"), "list": out}
    if action == "detail":
        lst = obj.get("list") or []
        v = lst[0] if lst else {}
        play = []
        # 兼容不同字段命名
        pf = v.get("vod_play_from", "")
        pu = v.get("vod_play_url", "")
        if pf and pu:
            froms = pf.split("$$$") if "$$$" in pf else [pf]
            for block in pu.split("$$$"):
                for line in block.split("#"):
                    if "$" in line:
                        play.append(line.split("$", 1)[1])
        return {"status": r["status"], "time_ms": r["time_ms"],
                "detail": {"vod_name": v.get("vod_name", ""), "play_urls": play}}


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "console.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                self._send(500, str(e))
        else:
            self._send(404, "not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}
        if self.path == "/api/test":
            res = do_request(body.get("url", ""), method=body.get("method", "GET"),
                             params=body.get("params"), body=body.get("body"),
                             headers=body.get("headers"))
            self._send(200, json.dumps(res, ensure_ascii=False))
        elif self.path == "/api/batch":
            items = body.get("items", [])
            out = []
            for it in items:
                r = do_request(it.get("url", ""), headers={"Referer": "https://www.baidu.com/"})
                if r.get("error"):
                    out.append({"name": it.get("name", ""), "url": it.get("url", ""), "ok": False, "detail": r["error"]})
                else:
                    out.append({"name": it.get("name", ""), "url": it.get("url", ""),
                                "status": r["status"], "time_ms": r["time_ms"], "ok": r["ok"],
                                "detail": (f"total 见响应" if r["ok"] else "非空但非JSON/XML")})
            self._send(200, json.dumps(out, ensure_ascii=False))
        elif self.path == "/api/maccms":
            res = maccms(body.get("base", ""), body.get("action", ""), body.get("ids"))
            self._send(200, json.dumps(res, ensure_ascii=False))
        else:
            self._send(404, "not found")

    def log_message(self, *args):
        pass  # 静默


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"测试操作台已启动： http://localhost:{PORT}  (Ctrl+C 退出)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
