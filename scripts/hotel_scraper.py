# -*- coding: utf-8 -*-
"""
酒店价格与全档案批量采集（拟人化、抗反爬）。

红线：只用真实已登录浏览器(bsk CLI)、只读渲染 DOM、不重放 API、不 headless、
遇验证码/登录墙交真人、拟人节奏、增量写盘 + 断点续跑。

用法：
  python hotel_scraper.py --probe
  python hotel_scraper.py --calibrate <url>
  python hotel_scraper.py --mode list [--limit N]
  python hotel_scraper.py --mode profile [--limit N] [--from-list URL] [--no-handoff]
  python hotel_scraper.py --mode discover --from-list URL
"""
from __future__ import annotations
import argparse, csv, json, os, random, re, shutil, subprocess, sys, time, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _pick_cfg_dir(root):
    """配置目录，按优先级探测，兼容三种布局：

    1. <root>/config                —— 本仓库/DSH 技能目录
    2. <root>/scripts/config        —— 深层嵌套（部分平台允许子目录）
    3. <root>/scripts               —— 配置平铺（平台限制两级目录时用）
    4. <root>                       —— 兜底
    """
    cands = [
        os.path.join(root, "config"),
        os.path.join(root, "scripts", "config"),
        os.path.join(root, "scripts"),
        root,
    ]
    for p in cands:
        if os.path.isfile(os.path.join(p, "settings.json")):
            return p
    return cands[0]

CFG = _pick_cfg_dir(HERE)
CF = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(*a):
    print("[%s]" % stamp(), *a, flush=True)

def resolve_config(name):
    """配置/输入文件名：绝对路径原样用，相对路径按技能根 config/ 解析。"""
    return name if os.path.isabs(name) else os.path.join(CFG, name)

def load_json(name):
    with open(resolve_config(name), "r", encoding="utf-8-sig") as f:
        return json.load(f)

def load_settings(name):
    """读配置并合并本机私有覆盖 settings.local.json（已被 .gitignore 排除，不发布）。"""
    cfg = load_json(name)
    local = os.path.join(os.path.dirname(resolve_config(name)), "settings.local.json")
    if os.path.exists(local):
        try:
            with open(local, "r", encoding="utf-8-sig") as f:
                ov = json.load(f)
            ov.pop("_note", None)
            cfg.update(ov)
            log("已合并本机覆盖", local)
        except Exception as e:
            log("本机覆盖读取失败(忽略):", repr(e))
    return cfg

def resolve_input(name, fallback=None):
    """输入清单：缺失时回退到可发布的 example 模板，保证 fresh clone 直接能跑。"""
    p = resolve_config(name)
    if not os.path.exists(p) and fallback:
        fp = resolve_config(fallback)
        if os.path.exists(fp):
            log("未找到 %s，改用 %s（占位示例）" % (name, fallback))
            return fp
    return p

def output_dir(cfg):
    """输出目录：环境变量 HOTEL_PROFILE_OUTPUT > 配置 output_dir > 默认 ./output。

    相对路径按技能根解析；技能包只读时（如宿主机只挂载只读目录）回退到当前工作目录。
    """
    env = os.environ.get("HOTEL_PROFILE_OUTPUT")
    if env:
        return os.path.abspath(env)
    d = cfg.get("output_dir") or "./output"
    if os.path.isabs(d):
        return d
    base = HERE if os.access(HERE, os.W_OK) else os.getcwd()
    return os.path.abspath(os.path.join(base, d))

def extract_json(text):
    if not text: return {}
    t = text.strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a: return {"_raw": t[:600]}
    try: return json.loads(t[a:b+1])
    except Exception: return {"_raw": t[:600], "_parse_error": True}

class Bsk:
    def __init__(self, cli, cfg):
        # bsk 不随本仓库发布：优先 PATH 查找；可用 BSK_CLI 或 settings.bsk_cli 覆盖绝对路径。
        cli = (os.environ.get("BSK_CLI") or cli or "bsk").strip()
        if not os.path.isabs(cli):
            found = shutil.which(cli)
            if not found:
                raise RuntimeError(
                    "找不到 bsk CLI。请把 bsk 加入 PATH、在 config/settings.json 设置 bsk_cli 绝对路径，"
                    "或设环境变量 BSK_CLI。安装见 https://github.com/Tencent/BrowserSkill")
            cli = found
        self.cli, self.cfg, self.sid = cli, cfg, None
        self.env = dict(os.environ); self.env["BSK_AUTO_START"] = "0"
        self.max_action = int(cfg.get("max_action_retries", 8))
        lo, hi = cfg.get("sync_backoff", [0.9, 1.6])
        self.backoff = (float(lo), float(hi))

    def run(self, args, timeout=60):
        cmd = [self.cli] + [str(a) for a in args]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout,
                               creationflags=CF, env=self.env)
            r = extract_json((p.stdout or "") + (("\n" + p.stderr) if p.stderr else ""))
            r["_rc"] = p.returncode
            return r
        except subprocess.TimeoutExpired:
            return {"code": "timeout"}
        except Exception as e:
            return {"code": "spawn_error", "message": repr(e)}

    def start(self, browser=None):
        a = ["session", "start", "--no-focus", "--json"]
        if browser: a += ["--browser", browser]
        r = self.run(a, 60)
        self.sid = r.get("session_id") or r.get("sessionId")
        if not self.sid:
            raise RuntimeError("session start 失败: %s" % json.dumps(r, ensure_ascii=False)[:400])
        return self.sid

    def stop(self):
        if self.sid:
            try: self.run(["session", "stop", self.sid, "--json"], 30)
            except Exception: pass

    def navigate(self, url, wait_until="domcontentloaded"):
        return self.run(["navigate", url, "--session", self.sid,
                         "--wait-until", wait_until, "--timeout", "60s", "--json"], 70)

    def sync(self):
        for _ in range(3):
            r = self.run(["cooperate", "sync", "--session", self.sid, "--settle",
                          "--max-tokens", "700", "--json"], 45)
            c = r.get("context_id") or r.get("contextId")
            if c: return c
            time.sleep(1.0)
        return None

    @staticmethod
    def retryable(r):
        if r.get("code"): return True
        m = (str(r.get("message", "")) + " " + str(r.get("error", ""))).lower()
        return any(k in m for k in ("synchronize", "frame changed", "content changed", "stale", "unknown for tab"))

    def action(self, sub, extra, depends=None):
        last = {}
        for _ in range(self.max_action):
            ctx = self.sync()
            if not ctx:
                time.sleep(1.5); continue
            a = [sub] + list(extra) + ["--session", self.sid, "--context", ctx, "--json"]
            for d in (depends or []): a += ["--depends-on", d]
            last = self.run(a, 60)
            if not self.retryable(last): return last
            time.sleep(random.uniform(*self.backoff))
        last["code"] = last.get("code") or "retry_exhausted"
        return last

    def evaluate(self, expr, depends=None):
        return self.action("evaluate", [expr], depends)

    def wheel(self, dy):
        return self.action("wheel", ["--delta-y", str(int(dy))])

    def fill(self, selector, value):
        return self.action("fill", ["--selector", selector, "--value", str(value)])

    def click(self, selector):
        return self.action("click", ["--selector", selector])

    def press(self, key, selector=None):
        # bsk press <KEY> 的键是位置参数，不是 --key
        a = [str(key)]
        if selector:
            a += ["--selector", selector]
        return self.action("press", a)

    def handoff(self, prompt, timeout_s=300):
        ctx = self.sync()
        a = ["request-help", "--session", self.sid, "--prompt", prompt,
             "--timeout", "%ds" % int(timeout_s), "--json"]
        if ctx: a += ["--context", ctx]
        return self.run(a, timeout_s + 30)

# ---------- DOM ----------
def build_extract_js(fields, container=None, max_rows=60, body_chars=2200):
    js = r"""(function(){
  var F = __FIELDS__, CON = __CONTAINER__, MAX = __MAX__;
  var roots = CON ? Array.from(document.querySelectorAll(CON)).slice(0, MAX) : [document];
  var pick = function(root, sels){
    for (var i=0;i<sels.length;i++){
      try {
        var els = root.querySelectorAll(sels[i]);
        if (els && els.length){
          var t=(els[0].innerText||els[0].textContent||'').trim().replace(/\s+/g,' ');
          if (t) return t;
        }
      } catch(e){}
    }
    return null;
  };
  var rows = roots.map(function(c){ var o={}; for (var k in F){ o[k]=pick(c, F[k]); } return o; });
  var bt = document.body.innerText||'';
  var lw = ["登录以查看","立即登录","请登录","登录查看","安全验证","请拖动","人机验证","访问验证"].filter(function(k){ return bt.indexOf(k)>=0; });
  return { rows: rows, __title: document.title, __url: location.href,
           __body: bt.slice(0, __BODY__), __login_wall: lw };
})()"""
    return (js.replace("__FIELDS__", json.dumps(fields, ensure_ascii=False))
              .replace("__CONTAINER__", json.dumps(container))
              .replace("__MAX__", str(int(max_rows)))
              .replace("__BODY__", str(body_chars)))

def build_calibrate_js(body_chars=1800):
    js = r"""(function(){
  var out={title:document.title, url:location.href};
  var prices=[]; var all=document.querySelectorAll('body *');
  for (var i=0;i<all.length;i++){
    var e=all[i]; if (e.children.length) continue;
    var t=(e.textContent||'').trim();
    if (/^[¥￥]?\s*\d{2,7}\s*(起|\/晚|元)?$/.test(t) && t.length<=14){
      prices.push({t:t, tag:e.tagName, cls:(typeof e.className==='string'?e.className:'').slice(0,90)});
      if (prices.length>=15) break;
    }
  }
  out.price_like=prices;
  var hints={};
  for (var j=0;j<all.length;j++){
    var c=all[j]; var cn=(typeof c.className==='string')?c.className:'';
    if (/hotel|name|title|price|score|rating|room|comment|review|address|star|tag/i.test(cn)){
      var key=cn.split(/\s+/)[0];
      if (key && hints[key]===undefined) hints[key]=(c.innerText||c.textContent||'').trim().replace(/\s+/g,' ').slice(0,90);
    }
  }
  out.class_hints=hints;
  out.body=(document.body.innerText||'').slice(0,__BODY__);
  return out;
})()"""
    return js.replace("__BODY__", str(body_chars))

RISK_KW = ["安全验证", "验证码", "滑动验证", "请拖动", "人机验证", "访问验证",
           "unusual traffic", "captcha", "请完成安全", "您的访问", "异常访问"]
def blocked(v):
    lw = v.get("__login_wall") or []
    if lw: return "登录/验证墙(" + "/".join(lw) + ")"
    s = (str(v.get("__body", "")) + " " + str(v.get("__title", ""))).lower()
    return next(("风控(" + k + ")" for k in RISK_KW if k.lower() in s), None)

PRICE = re.compile(r"[¥￥]\s*(\d[\d,]*)(?:\.\d+)?")
def to_price(s):
    if not s: return None
    m = PRICE.search(str(s))
    return int(m.group(1).replace(",", "")) if m else None

def to_num(s):
    if not s: return None
    m = re.search(r"(\d[\d,]*)", str(s).replace(",", ""))
    return int(m.group(1)) if m else None

def normalise(raw, keys, base):
    row = dict(base)
    for k in keys: row[k] = raw.get(k)
    row["price_num"] = to_price(raw.get("sale_price") or raw.get("price"))
    row["rating_num"] = None
    m = re.search(r"(\d(?:\.\d)?)", str(raw.get("rating") or ""))
    if m: row["rating_num"] = float(m.group(1))
    row["review_num"] = to_num(raw.get("review_count"))
    return row

# ---------- URL / IO ----------
def fmt_date(d, cfg):
    return str(d or "").strip().replace("-", cfg.get("date_sep", "/"))

def build_url(row, cfg, mode):
    if row.get("url"): return row["url"]
    ci = fmt_date(row.get("checkin") or cfg.get("checkin"), cfg)
    co = fmt_date(row.get("checkout") or cfg.get("checkout"), cfg)
    tpl = cfg.get("detail_url_template") if mode == "detail" else cfg.get("list_url_template")
    tpl = (tpl or "").replace("{base_url}", cfg.get("base_url") or "")
    return (tpl.replace("{hotel_id}", str(row.get("hotel_id") or row.get("platform_hotel_id") or ""))
               .replace("{city_id}", str(row.get("city_id") or "2"))
               .replace("{checkin}", ci).replace("{checkout}", co))

def read_hotels(cfg):
    p = resolve_input(cfg.get("hotels_csv", "hotels.csv"), "hotels.example.csv")
    if not os.path.exists(p): return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

COLS = ["capture_time", "mode", "city", "hotel_name", "platform_hotel_id", "star",
        "rating", "rating_num", "review_count", "review_num", "address",
        "checkin", "checkout", "nights", "guests_rooms", "room_type", "bed_type",
        "area", "breakfast", "cancellation", "price", "sale_price", "list_price",
        "price_num", "currency", "tax_included", "promo_tags", "availability",
        "source_url", "status", "notes"]

def row_key(row, mode, cfg):
    return "|".join([str(row.get("url") or row.get("hotel_id") or row.get("city_id") or ""),
                     str(row.get("checkin") or cfg.get("checkin") or ""),
                     str(row.get("checkout") or cfg.get("checkout") or ""), mode])

def save_progress(p, done):
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done), "updated": stamp()}, f, ensure_ascii=False, indent=2)

def jitter(pair):
    time.sleep(random.uniform(float(pair[0]), float(pair[1])))

def human_scroll(b, pace):
    for _ in range(random.randint(1, int(pace.get("wheel_steps_max", 2)))):
        b.wheel(random.randint(120, 380))
        time.sleep(random.uniform(0.3, 0.9))

# ---------- 模式 ----------
def do_probe(b, cfg):
    log("连通性 / 协作协议自检")
    base = (cfg.get("base_url") or "").rstrip("/")
    if not base:
        log("未指定目标站点，自检改为只验证浏览器会话可用（不打开网页）")
    b.navigate(cfg.get("probe_url") or (base + "/" if base else "about:blank"))
    jitter(cfg.get("pace", {}).get("after_navigate", [1.5, 3.0]))
    r = b.evaluate("(function(){return {title:document.title,url:location.href,bodyLen:(document.body.innerText||'').length}})()")
    v = r.get("value") if isinstance(r.get("value"), dict) else r
    ok = isinstance(v, dict) and bool(v.get("title")) and not r.get("code")
    log("结果:", "OK" if ok else "FAIL", json.dumps(v, ensure_ascii=False)[:400])
    if not ok: log("原始返回:", json.dumps(r, ensure_ascii=False)[:600])
    return 0 if ok else 1

def do_calibrate(b, cfg, url):
    log("校准:", url)
    b.navigate(url)
    jitter(cfg.get("pace", {}).get("after_navigate", [2.0, 4.0]))
    human_scroll(b, cfg.get("pace", {}))
    r = b.evaluate(build_calibrate_js())
    v = r.get("value") if isinstance(r.get("value"), dict) else r
    out = os.path.join(output_dir(cfg), "calibration.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"url": url, "at": stamp(), "result": v, "raw": r}, f, ensure_ascii=False, indent=2)
    log("已导出 ->", out)
    print(json.dumps(v, ensure_ascii=False, indent=2)[:3500])
    return 0

def do_batch(b, cfg, sel, args):
    mode = args.mode or cfg.get("mode", "list")
    fields = sel.get(mode) or sel.get("list") or {}
    container = sel.get(mode + "_container")
    out_dir = output_dir(cfg)
    os.makedirs(out_dir, exist_ok=True)
    csv_p = os.path.join(out_dir, "sale_prices.csv")
    jsonl_p = os.path.join(out_dir, "sale_prices.jsonl")
    prog_p = os.path.join(out_dir, "progress.json")
    new = not os.path.exists(csv_p) or os.path.getsize(csv_p) == 0
    fc = open(csv_p, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fc, fieldnames=COLS, extrasaction="ignore")
    if new: w.writeheader()
    fj = open(jsonl_p, "a", encoding="utf-8")
    done = set()
    if os.path.exists(prog_p):
        try: done = set(json.load(open(prog_p, encoding="utf-8")).get("done", []))
        except Exception: pass
    hotels = read_hotels(cfg)
    order = list(range(len(hotels)))
    if cfg.get("shuffle", True): random.shuffle(order)
    cap = args.limit or int(cfg.get("max_per_run", 0)) or len(order)
    pace = cfg.get("pace", {})
    allow_handoff = bool(cfg.get("allow_handoff", True)) and not args.no_handoff
    depends = cfg.get("evaluate_depends_on") or []
    expr = build_extract_js(fields, container, int(cfg.get("max_rows_per_page", 60)))
    n = 0
    try:
        for i in order:
            if n >= cap: break
            row = hotels[i]
            key = row_key(row, mode, cfg)
            if key in done: continue
            url = build_url(row, cfg, mode)
            log("(%d/%d) %s" % (n + 1, min(cap, len(order)), row.get("hotel_name") or row.get("hotel_id") or url))
            base = {"capture_time": stamp(), "mode": mode, "city": row.get("city", ""),
                    "hotel_name": row.get("hotel_name", ""),
                    "platform_hotel_id": row.get("hotel_id") or row.get("platform_hotel_id") or "",
                    "checkin": row.get("checkin") or cfg.get("checkin", ""),
                    "checkout": row.get("checkout") or cfg.get("checkout", ""),
                    "guests_rooms": cfg.get("guests_rooms", "1间,2成人"),
                    "room_type": row.get("room_type", ""), "currency": "CNY",
                    "source_url": url}
            try:
                b.navigate(url)
                jitter(pace.get("after_navigate", [1.5, 3.2]))
                human_scroll(b, pace)
                jitter(pace.get("dwell", [1.0, 2.6]))
                r = b.evaluate(expr, depends=depends)
                v = r.get("value") if isinstance(r.get("value"), dict) else {}
                rows = v.get("rows") or []
                hit = blocked(v)
                if hit and allow_handoff:
                    log("检测到 %s，交真人处理..." % hit)
                    b.handoff("目标站点需要登录账号或完成安全验证才能看到价格。请在真实浏览器里登录/验证，完成后回到此任务。", cfg.get("handoff_timeout", 300))
                    jitter([1.5, 3.0])
                    r = b.evaluate(expr, depends=depends)
                    v = r.get("value") if isinstance(r.get("value"), dict) else {}
                    rows = v.get("rows") or []
                    if not blocked(v): hit = None
                if (not rows) or r.get("code"):
                    recs = [dict(base, status=("blocked" if hit else "failed"), notes=str(hit or r.get("code") or "no data"))]
                else:
                    recs = []
                    for raw in rows:
                        rec = normalise(raw, list(fields.keys()), base)
                        rec["status"] = "ok" if (rec.get("price_num") or raw.get("hotel_name")) else "partial"
                        if hit:
                            rec["status"] = "needs_login"; rec["notes"] = hit
                        recs.append(rec)
                for rec in recs:
                    w.writerow(rec); fc.flush()
                    fj.write(json.dumps(rec, ensure_ascii=False) + "\n"); fj.flush()
                done.add(key); save_progress(prog_p, done)
                n += 1
                log("  -> %d 行, 状态 %s, 首行 %s" % (len(recs), recs[0].get("status"), recs[0].get("hotel_name") or ""))
            except Exception as e:
                log("  异常跳过:", repr(e))
                rec = dict(base); rec["status"] = "error"; rec["notes"] = repr(e)
                w.writerow(rec); fc.flush()
                done.add(key); save_progress(prog_p, done)
                n += 1
            jitter(pace.get("between_hotels", [2.2, 4.8]))
            if cfg.get("long_rest_every") and n % int(cfg["long_rest_every"]) == 0:
                log("分批长休息..."); jitter(pace.get("long_rest", [25, 55]))
    finally:
        fc.close(); fj.close()
    if cfg.get("write_xlsx", True):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
            wb = Workbook(); ws = wb.active; ws.title = "酒店价格"
            with open(csv_p, "r", encoding="utf-8") as f:
                for rr in csv.reader(f): ws.append(rr)
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="2F5496")
            ws.freeze_panes = "A2"
            wb.save(os.path.join(out_dir, "sale_prices.xlsx"))
        except Exception as e:
            log("xlsx 生成失败(不影响 CSV):", repr(e))
    return n, csv_p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--calibrate")
    ap.add_argument("--mode", choices=["list", "detail", "profile", "discover", "match"],
                    help="list=列表页价格快照; profile/detail=详情页全档案; discover=从列表页提取 hotelId")
    ap.add_argument("--from-list", help="profile 模式：先从该列表页 URL 发现 hotelId 再逐家取全档案")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--base-url", help="目标站点根地址，覆盖 config 里的 base_url")
    ap.add_argument("--input", help="match 模式：用户导入的酒店清单（csv / xlsx）")
    ap.add_argument("--no-pool", action="store_true", help="match 模式：不滚动收集候选池，改为按名称逐个搜索")
    ap.add_argument("--name-column", help="match 模式：清单里酒店名称所在的列名（不填则自动识别）")
    ap.add_argument("--no-handoff", action="store_true", help="后台定时跑：遇登录/验证码只记状态不阻塞")
    ap.add_argument("--settings")
    a = ap.parse_args()
    cfg = load_settings(a.settings or "settings.json")
    if getattr(a, "base_url", None):
        cfg["base_url"] = a.base_url.rstrip("/")
    sel = load_json("selectors.json")
    if not (cfg.get("base_url") or "").strip():
        log("未指定目标站点。两种做法任选其一：")
        log("  1) 命令行加参数：--base-url <站点根地址>，例如 --base-url https://example.com")
        log("  2) 写进配置：scripts/config/settings.json 的 base_url")
        log("（本技能不绑定具体站点，站点地址由使用者提供）")
        return 2
    if a.mode == "match":
        import match_hotels
        return match_hotels.run_match(cfg, sel, a)
    if a.mode in ("profile", "detail", "discover"):
        import hotel_profile
        return hotel_profile.run(cfg, sel, a)
    b = Bsk(cfg.get("bsk_cli"), cfg)
    sid = b.start(cfg.get("browser_instance") or None)
    log("bsk session", sid)
    rc = 0
    try:
        if a.probe: rc = do_probe(b, cfg)
        elif a.calibrate: rc = do_calibrate(b, cfg, a.calibrate)
        else:
            n, p = do_batch(b, cfg, sel, a)
            log("采集完成 %d 个目标 -> %s" % (n, p))
    finally:
        b.stop()
    return rc

if __name__ == "__main__":
    sys.exit(main())
