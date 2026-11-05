# coding=utf-8
# 资源站 / 解析接口 测试操作台 —— 后端（仅用 Python 标准库，零依赖）
# 启动：python web_console.py  然后浏览器打开 http://localhost:8000
import http.server, json, urllib.request, urllib.error, ssl, time, os, re
import sys, types, importlib.util, uuid, tempfile, traceback
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


# ============================================================
# Python 引擎测试：桩掉 base.spider，动态加载并调用引擎的 Spider 方法
# 警告：会执行用户提供的任意 Python 代码，仅用于本地、且你信任的引擎。
# ============================================================
_STUB_SPIDER = '''
import urllib.request, urllib.parse, urllib.error, json as _json
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

class Spider:
    def __init__(self, *a, **k):
        self.extend = ""
    def init(self, extend=""):
        self.extend = extend or ""
    def _req(self, url, method="GET", headers=None, params=None, data=None, timeout=15):
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        h = {"User-Agent": _UA}
        if headers: h.update(headers)
        body = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = _json.dumps(data).encode(); h.setdefault("Content-Type","application/json")
            elif isinstance(data, str):
                body = data.encode()
            else:
                body = data
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.getcode(), r.headers.get("Content-Type","")
    def fetch(self, url, headers=None, params=None, data=None, method="GET", verify=True, timeout=15):
        try:
            txt, code, ct = self._req(url, method=method, headers=headers, params=params, data=data, timeout=timeout)
        except urllib.error.HTTPError as e:
            try: return e.read().decode("utf-8","replace")
            except Exception: return ""
        except Exception:
            raise
        return txt
    def post(self, url, data=None, headers=None, params=None, timeout=15):
        return self.fetch(url, headers=headers, params=params, data=data, method="POST", timeout=timeout)
    def evaluate(self, js_code):
        raise NotImplementedError("stub: evaluate() 需要框架的 JS 运行时；依赖它的引擎请在真框架中测试")
    def js(self, *a, **k):
        raise NotImplementedError("stub: js() 未实现")
    def download(self, *a, **k):
        raise NotImplementedError("stub: download() 未实现")
    def saveCache(self, *a, **k): pass
    def getCache(self, *a, **k): return None
    def db(self, *a, **k): return None
    def push(self, *a, **k): pass
    def log(self, *a, **k):
        import sys; print(*a, file=sys.stderr)
'''

_BASE_PREPARED = False
def _prepare_base_stub():
    """把 base.spider 桩注入 sys.modules（只需一次）。"""
    global _BASE_PREPARED
    if _BASE_PREPARED:
        return
    base = types.ModuleType("base")
    spider_mod = types.ModuleType("base.spider")
    exec(compile(_STUB_SPIDER, "base.spider", "exec"), spider_mod.__dict__)
    base.spider = spider_mod
    sys.modules["base"] = base
    sys.modules["base.spider"] = spider_mod
    _BASE_PREPARED = True

def _summarize(obj, maxlen=500):
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s[:maxlen]

def _find_spider(mod, spider_mod):
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, spider_mod.Spider) and obj is not spider_mod.Spider:
            return obj
    return None

def _validate_schema(method, result):
    notes = []
    if not isinstance(result, dict):
        return {"ok": False, "notes": ["返回不是 dict（TVBox 期望 dict）"]}
    if method in ("homeContent", "categoryContent", "detailContent", "searchContent"):
        if "list" not in result:
            notes.append("缺少 list 字段")
        else:
            l = result["list"]
            if not isinstance(l, list):
                notes.append("list 不是 list")
            elif l and not isinstance(l[0], dict):
                notes.append("list[0] 不是 dict")
    if method == "playerContent":
        if "playUrl" not in result and "url" not in result:
            notes.append("缺少 playUrl/url")
        if "parse" not in result:
            notes.append("缺少 parse 字段（0=直链 / 1=需二次解析）")
    return {"ok": len(notes) == 0, "notes": notes}

def _run_engine_method(inst, method, args):
    fn = getattr(inst, method, None)
    if not fn:
        return None, f"引擎未实现方法 {method}"
    return fn(*(args or []))  # 可能抛异常，由外层捕获

def _run_engine_chain(inst):
    steps = []
    try:
        home = inst.homeContent(False)
        steps.append({"step": "homeContent", "ok": isinstance(home, dict), "sample": _summarize(home)})
    except Exception as e:
        steps.append({"step": "homeContent", "ok": False, "error": str(e)[:200]})
        return None, steps
    lst = (home or {}).get("list") or []
    if not lst:
        steps.append({"step": "detailContent", "ok": False, "error": "homeContent 未返回 list"})
        return home, steps
    vid = (lst[0] or {}).get("vod_id")
    try:
        det = inst.detailContent([vid])
        steps.append({"step": "detailContent", "ok": isinstance(det, dict), "sample": _summarize(det)})
    except Exception as e:
        steps.append({"step": "detailContent", "ok": False, "error": str(e)[:200]})
        return home, steps
    dlst = (det or {}).get("list") or []
    purl = (dlst[0] or {}).get("vod_play_url") if dlst else None
    if not purl:
        steps.append({"step": "playerContent", "ok": False, "error": "detail 未返回 vod_play_url"})
        return home, steps
    first = str(purl).split("#")[0]
    if "$" in first:
        parts = first.split("$")
        flag = parts[0]; url = "$".join(parts[1:])
    else:
        flag, url = "", first
    pc = None
    try:
        pc = inst.playerContent(flag, url, "")
        steps.append({"step": "playerContent", "ok": isinstance(pc, dict), "sample": _summarize(pc)})
    except Exception as e:
        steps.append({"step": "playerContent", "ok": False, "error": str(e)[:200]})
    return {"home": home, "detail": det, "player": pc}, steps

def run_engine(code, method, args, mode="method"):
    _prepare_base_stub()
    spider_mod = sys.modules["base.spider"]
    modname = "eng_" + uuid.uuid4().hex
    path = os.path.join(tempfile.gettempdir(), modname + ".py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    logs = []
    SpiderCls = None
    result = None
    steps = []
    err = None
    builtins = __import__("builtins")
    orig_print = builtins.print
    builtins.print = lambda *a, **k: logs.append(" ".join(str(x) for x in a))
    try:
        spec = importlib.util.spec_from_file_location(modname, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        SpiderCls = _find_spider(mod, spider_mod)
        if not SpiderCls:
            err = "未找到继承自 base.spider.Spider 的类"
        else:
            inst = SpiderCls()
            if mode == "chain":
                result, steps = _run_engine_chain(inst)
            else:
                try:
                    result = _run_engine_method(inst, method, args)
                    steps = [{"step": method, "ok": True}]
                except Exception:
                    err = traceback.format_exc()
    except Exception:
        err = traceback.format_exc()
    finally:
        builtins.print = orig_print
        for k in list(sys.modules):
            if k == modname or k.startswith(modname + "."):
                del sys.modules[k]
        try:
            os.remove(path)
        except Exception:
            pass
    schema = None
    if mode != "chain" and result is not None and not err:
        schema = _validate_schema(method, result)
    return {
        "class": SpiderCls.__name__ if SpiderCls else None,
        "method": method, "mode": mode,
        "result": result, "steps": steps,
        "schema": schema, "logs": logs[:50], "error": err,
    }


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
        elif self.path == "/api/engine":
            code = body.get("code", "")
            method = body.get("method", "homeContent")
            args = body.get("args", [])
            mode = body.get("mode", "method")
            if not code.strip():
                self._send(200, json.dumps({"error": "请先粘贴引擎代码"}, ensure_ascii=False))
            else:
                res = run_engine(code, method, args, mode)
                self._send(200, json.dumps(res, ensure_ascii=False, default=str))
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
