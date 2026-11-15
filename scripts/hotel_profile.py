# -*- coding: utf-8 -*-
"""
酒店全档案采集：房型 / 周边配套 / 设施(会议室·泳池·健身房…) / 政策 / 基本信息。

--mode profile   逐家打开详情页，输出「酒店概览 + 房型 + 周边配套」三张表
--mode discover  从列表页提取 hotelId 清单，供批量使用

复用 hotel_scraper 的 Bsk 客户端、拟人节奏、登录墙判定与增量写盘。
每家酒店用独立 bsk 会话（抗反爬也更像真人逐页打开）。
"""
from __future__ import annotations
import os, sys, re, json, csv, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hotel_scraper as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = C.CFG  # 与主驱动一致：<root>/config 或 <root>/scripts/config
JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_extract.js")

PROFILE_COLS = ["capture_time", "platform_hotel_id", "hotel_name", "city", "address", "phone",
                "rating", "review_count", "room_type_count", "facilities",
                "has_meeting_room", "has_pool", "has_gym", "has_parking", "has_restaurant",
                "has_spa", "has_airport_shuttle", "has_wifi", "has_bar",
                "nearby_summary", "nearby_poi_count", "metro", "intro", "highlights",
                "policy", "breakfast_policy", "checkin", "checkout", "source_url", "status", "notes"]

ROOM_COLS = ["capture_time", "platform_hotel_id", "hotel_name", "room_name", "bed_type",
             "area_sqm", "floor", "window", "smoke", "wifi", "price_num", "price_text",
             "breakfast", "cancellation", "availability", "checkin", "checkout"]

NEARBY_COLS = ["capture_time", "platform_hotel_id", "hotel_name", "category", "poi_name", "distance"]

FLAG_KW = {
    "has_meeting_room": ["会议室", "会议厅", "宴会厅", "会议空间", "商务中心"],
    "has_pool": ["泳池", "游泳池", "室内泳池", "室外泳池", "无边泳池"],
    "has_gym": ["健身房", "健身中心", "健身室", "健身器材"],
    "has_parking": ["停车场", "停车位", "充电车位", "停车"],
    "has_restaurant": ["餐厅", "中餐厅", "西餐厅", "咖啡厅", "自助餐"],
    "has_spa": ["SPA", "spa", "水疗", "桑拿", "足浴"],
    "has_airport_shuttle": ["接送机", "机场接送", "接站", "班车", "送机"],
    "has_wifi": ["wifi", "Wi-Fi", "无线上网", "公用区wifi"],
    "has_bar": ["酒吧", "大堂吧", "酒廊", "示例吧"],
}

DISCOVER_JS = r"""(function(){
  var out = [], seen = {};
  var cards = document.querySelectorAll('.hotel-card,[class*=hotelCard],[class*=hotel-list-item]');
  Array.from(cards).forEach(function(c){
    var id = c.id || c.getAttribute('data-hotel-id') || c.getAttribute('data-id') || '';
    if (!/^\d+$/.test(id)) {
      var a = c.querySelector('a[href*="hotelId"]');
      if (a) { var mm = a.getAttribute('href').match(/hotelId=(\d+)/); if (mm) id = mm[1]; }
    }
    var ne = c.querySelector('[class*=hotelName],[class*=hotel-title],h3,h2');
    var name = ne ? (ne.innerText||'').trim() : '';
    if (/^\d+$/.test(id) && !seen[id]) { seen[id]=1; out.push({id:id, name:name.slice(0,60)}); }
  });
  if (!out.length) {
    var html = document.documentElement.innerHTML || '';
    var re = /hotelId[=:"'\s]+(\d{4,12})/g, m;
    while ((m = re.exec(html)) !== null && out.length < 60) {
      if (!seen[m[1]]) { seen[m[1]]=1; out.push({id:m[1], name:''}); }
    }
  }
  var named = [];
  Array.from(document.querySelectorAll('[id]')).forEach(function(e){
    if (/^\d{6,12}$/.test(e.id) && named.indexOf(e.id) < 0) named.push(e.id);
  });
  return { items: out.slice(0, 60), namedIds: named.slice(0, 60) };
})()"""

def build_js(fields):
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()
    return js.replace("__FIELDS__", json.dumps(fields, ensure_ascii=False))

# --------------------------- 纯解析函数（可用真实快照离线验证） ---------------------------
def parse_room(text):
    t = (text or "").strip()
    if len(t) < 8: return None
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    name = lines[0] if lines else ""
    if re.match(r"^\d+$", name) and len(lines) > 1: name = lines[1]
    name = re.sub(r"\d+$", "", name).strip()
    if not name: return None
    bed = re.search(r"(\d+张[^，,|\n]{0,40}?床)", t)
    area = re.search(r"(\d+(?:\.\d+)?)\s*平方米", t)
    floor = re.search(r"(\d+(?:-\d+)?层)", t)
    price = re.search(r"[¥￥]\s*([\d,]+)", t)
    bf = re.search(r"(无早餐|含早餐|\d+份早餐|双早|单早|自助早餐)", t)
    cxl = re.search(r"([^\n]{0,30}取消[^\n]{0,20})", t)
    avail = re.search(r"(仅剩\d+间|房量紧张|满房|售罄|至多\d+间|有房)", t)
    return {
        "room_name": name[:60],
        "bed_type": bed.group(1) if bed else "",
        "area_sqm": area.group(1) if area else "",
        "floor": floor.group(1) if floor else "",
        "window": "有窗" if "有窗" in t else ("无窗" if "无窗" in t else ""),
        "smoke": "禁烟" if "禁烟" in t else "",
        "wifi": "免费" if re.search(r"Wi-?Fi免费|免费Wi-?Fi", t, re.I) else ("有" if re.search(r"wi-?fi", t, re.I) else ""),
        "price_num": int(price.group(1).replace(",", "")) if price else "",
        "price_text": price.group(0) if price else "",
        "breakfast": bf.group(1) if bf else "",
        "cancellation": cxl.group(1).strip() if cxl else "",
        "availability": avail.group(1) if avail else "",
    }

def parse_nearby(text):
    t = text or ""
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    out, cur = [], None
    for l in lines:
        if l in ("附近", "在地图上查看"): continue
        m = re.match(r"^([^\s:：]{2,10})\s*[:：]\s*(.+)$", l)
        if m:
            poi = m.group(2).strip()
            dist = ""
            dm = re.search(r"[（(]\s*([\d.]+\s*(?:公里|米|km|m))\s*[）)]", poi)
            if dm:
                dist = dm.group(1).strip()
                poi = poi[:dm.start()].strip()
            cur = {"category": m.group(1).strip(), "poi_name": poi, "distance": dist}
            out.append(cur)
            continue
        d = re.match(r"^[（(]?\s*([\d.]+\s*(?:公里|米|km|m))\s*[）)]?$", l)
        if d and cur:
            cur["distance"] = d.group(1).strip()
            cur = None
    return [x for x in out if x["poi_name"] and x["poi_name"] not in ("附近", "在地图上查看")]

def derive_flags(text):
    t = text or ""
    return {k: ("是" if any(w in t for w in kws) else "否") for k, kws in FLAG_KW.items()}

def flatten(v, base):
    one = v.get("one") or {}
    lng = v.get("longest") or {}
    al = v.get("all") or {}
    items = [x for x in (al.get("facility_items") or []) if x]
    fac = " | ".join([x for x in [(lng.get("facilities") or ""), ("、".join(items[:80]))] if x])
    rooms, rseen = [], set()
    for r in (parse_room(t) for t in (al.get("rooms") or [])):
        if r and r["room_name"] not in rseen:
            rseen.add(r["room_name"]); rooms.append(r)
    nb_text = v.get("nearby_block") or lng.get("nearby") or ""
    pois = parse_nearby(nb_text)
    score = one.get("score") or ""
    body_head = (v.get("body") or "")[:4000]
    # 详情页评分在正文里是独立一行「4.8」+「超棒」；score 字段是「超棒 7,014 条评论」，别把 7 当评分
    rm = re.search(r"(\d\.\d)\s*(?:超棒|很好|不错|棒|赞)", body_head) or re.search(r"(?m)^(\d\.\d)\s*$", body_head)
    cm = re.search(r"([\d,]+)\s*条\s*(?:点评|评论)", body_head) or re.search(r"([\d,]+)\s*条", score)
    row = dict(base)
    row.update(derive_flags(fac))
    row.update({
        "hotel_name": one.get("hotel_name") or base.get("hotel_name") or "",
        "address": one.get("address") or "",
        "phone": (one.get("phone") or "").replace("电话：", "").strip(),
        "rating": rm.group(1) if rm else "",
        "review_count": cm.group(1) if cm else "",
        "room_type_count": len(rooms),
        "facilities": fac[:6000],
        "nearby_summary": "；".join(["%s:%s(%s)" % (p["category"], p["poi_name"], p["distance"] or "—") for p in pois])[:2000],
        "nearby_poi_count": len(pois),
        "metro": one.get("metro") or "",
        "intro": v.get("intro_block") or lng.get("intro") or "",
        "highlights": "、".join((al.get("highlights") or [])[:20]),
        "policy": (lng.get("policy") or "")[:4000],
        "breakfast_policy": one.get("breakfast_policy") or "",
    })
    return row, rooms, pois

# --------------------------- IO ---------------------------
class Sink:
    def __init__(self, path, cols):
        new = not os.path.exists(path) or os.path.getsize(path) == 0
        self.f = open(path, "a", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=cols, extrasaction="ignore")
        if new: self.w.writeheader()
    def put(self, row):
        self.w.writerow(row); self.f.flush()
    def close(self): self.f.close()

def write_xlsx(out_dir):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook(); wb.remove(wb.active)
        for sheet, fn in [("酒店概览", "hotel_profiles.csv"), ("房型", "hotel_rooms.csv"), ("周边配套", "hotel_nearby.csv")]:
            ws = wb.create_sheet(sheet)
            p = os.path.join(out_dir, fn)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for r in csv.reader(f): ws.append(r)
            for c in ws[1]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="2F5496")
                c.alignment = Alignment(vertical="center")
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
        wb.save(os.path.join(out_dir, "hotel_report.xlsx"))
    except Exception as e:
        C.log("xlsx 生成失败(不影响 CSV):", repr(e))

def read_profile_hotels(cfg):
    p = C.resolve_input(cfg.get("profile_hotels_csv", "hotels.profile.csv"),
                        "hotels.profile.example.csv")
    if not os.path.exists(p): return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if (r.get("hotel_id") or "").strip() or "/detail" in (r.get("url") or "")]

def discover_ids(cfg, url):
    b = C.Bsk(cfg.get("bsk_cli"), cfg)
    sid = b.start(cfg.get("browser_instance") or None)
    try:
        C.log("发现 hotelId:", url, "session", sid)
        b.navigate(url)
        C.jitter([3.0, 4.5])
        for dy in (400, 600):
            b.wheel(dy); C.jitter([0.8, 1.3])
        r = b.evaluate(DISCOVER_JS)
        v = r.get("value") if isinstance(r.get("value"), dict) else {}
        items = v.get("items") or []
        if not items:
            items = [{"id": x, "name": ""} for x in (v.get("namedIds") or [])]
        C.log("  发现", len(items), "个 hotelId")
        return items
    finally:
        b.stop()

def do_discover(cfg, sel, a, out_dir):
    url = a.from_list or cfg.get("list_url_template", "").replace("{city_id}", "2")
    url = url.replace("{checkin}", C.fmt_date(cfg.get("checkin"), cfg)).replace("{checkout}", C.fmt_date(cfg.get("checkout"), cfg))
    items = discover_ids(cfg, url)
    p = os.path.join(out_dir, "discovered_hotels.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "url", "city_id", "city", "hotel_name", "checkin", "checkout", "room_type", "note"])
        w.writeheader()
        for x in items:
            w.writerow({"hotel_id": x["id"], "hotel_name": x.get("name") or "", "city": cfg.get("default_city", "上海"), "note": "由 --mode discover 自动发现"})
    C.log("已写入", p, "共", len(items), "行；复制到 config/hotels.profile.csv 后跑 --mode profile")
    return 0 if items else 1

def run(cfg, sel, a):
    out_dir = C.output_dir(cfg)
    os.makedirs(out_dir, exist_ok=True)
    if a.mode == "discover":
        return do_discover(cfg, sel, a, out_dir)

    fields = sel.get("profile") or {}
    js = build_js(fields)
    rows = read_profile_hotels(cfg)
    if a.from_list:
        rows = [{"hotel_id": x["id"], "hotel_name": x.get("name") or "", "city": "",
                 "checkin": cfg.get("checkin", ""), "checkout": cfg.get("checkout", ""), "url": ""}
                for x in discover_ids(cfg, a.from_list)]
    if not rows:
        C.log("没有可采集的酒店：请在 config/%s 填 hotel_id，或用 --from-list <列表页URL>" % cfg.get("profile_hotels_csv", "hotels.profile.csv"))
        return 1

    sp = Sink(os.path.join(out_dir, "hotel_profiles.csv"), PROFILE_COLS)
    sr = Sink(os.path.join(out_dir, "hotel_rooms.csv"), ROOM_COLS)
    sn = Sink(os.path.join(out_dir, "hotel_nearby.csv"), NEARBY_COLS)
    prog_p = os.path.join(out_dir, "progress_profile.json")
    done = set()
    if os.path.exists(prog_p):
        try: done = set(json.load(open(prog_p, encoding="utf-8")).get("done", []))
        except Exception: pass
    def save_done():
        with open(prog_p, "w", encoding="utf-8") as f:
            json.dump({"done": sorted(done), "updated": C.stamp()}, f, ensure_ascii=False, indent=2)

    order = list(range(len(rows)))
    if cfg.get("shuffle", True): random.shuffle(order)
    cap = a.limit or int(cfg.get("max_per_run", 0)) or len(order)
    pace = cfg.get("pace", {})
    allow = bool(cfg.get("allow_handoff", True)) and not a.no_handoff
    depends = cfg.get("evaluate_depends_on") or []
    n = 0
    try:
        for i in order:
            if n >= cap: break
            row = rows[i]
            hid = (row.get("hotel_id") or "").strip()
            ci = row.get("checkin") or cfg.get("checkin", "")
            co = row.get("checkout") or cfg.get("checkout", "")
            key = "|".join([hid or row.get("url", ""), ci, co, "profile"])
            if key in done: continue
            url = row.get("url") or C.build_url(row, cfg, "detail")
            C.log("(%d/%d) %s %s" % (n + 1, min(cap, len(order)), hid, row.get("hotel_name") or ""))
            base = {"capture_time": C.stamp(), "platform_hotel_id": hid,
                    "hotel_name": row.get("hotel_name", ""), "city": row.get("city", ""),
                    "checkin": ci, "checkout": co, "source_url": url}
            b = C.Bsk(cfg.get("bsk_cli"), cfg)
            try:
                b.start(cfg.get("browser_instance") or None)
            except Exception as e:
                C.log("  会话启动失败:", repr(e))
                sp.put(dict(base, status="failed", notes=repr(e)))
                done.add(key); save_done(); n += 1
                continue
            try:
                nav = b.navigate(url)
                if nav.get("code"):
                    C.log("  导航返回:", str(nav.get("code")))
                C.jitter(pace.get("after_navigate", [2.0, 3.5]))
                C.human_scroll(b, pace)
                for dy in (600, 800):
                    b.wheel(dy); C.jitter([0.9, 1.6])
                C.jitter(pace.get("dwell", [1.0, 2.2]))
                r = b.evaluate(js, depends=depends)
                v = r.get("value") if isinstance(r.get("value"), dict) else {}
                hit = C.blocked({"__login_wall": v.get("login_wall"), "__body": v.get("body"), "__title": v.get("title")})
                if hit and allow:
                    C.log("  检测到 %s，交真人处理..." % hit)
                    b.handoff("目标站点需要登录或完成验证才能查看酒店详情。请在真实浏览器里处理完后回到此任务。", cfg.get("handoff_timeout", 300))
                    C.jitter([1.5, 3.0])
                    r = b.evaluate(js, depends=depends)
                    v = r.get("value") if isinstance(r.get("value"), dict) else {}
                    if not C.blocked({"__login_wall": v.get("login_wall"), "__body": v.get("body"), "__title": v.get("title")}): hit = None
                if not v or r.get("code"):
                    sp.put(dict(base, status="failed", notes=str(hit or r.get("code") or "no data")))
                    C.log("  -> failed", str(hit or r.get("code") or "no data"))
                else:
                    pr, rms, pois = flatten(v, base)
                    pr["status"] = "ok" if pr.get("hotel_name") else "partial"
                    if hit: pr["status"] = "needs_login"; pr["notes"] = hit
                    sp.put(pr)
                    for rm in rms:
                        sr.put(dict(rm, capture_time=pr["capture_time"], platform_hotel_id=hid,
                                    hotel_name=pr["hotel_name"], checkin=ci, checkout=co))
                    for p in pois:
                        sn.put(dict(p, capture_time=pr["capture_time"], platform_hotel_id=hid, hotel_name=pr["hotel_name"]))
                    C.log("  -> %s | 房型 %d | 周边 %d | 会议室 %s 泳池 %s" %
                          (pr["status"], len(rms), len(pois), pr["has_meeting_room"], pr["has_pool"]))
            except Exception as e:
                C.log("  异常跳过:", repr(e))
                sp.put(dict(base, status="error", notes=repr(e)))
            finally:
                b.stop()
            done.add(key); save_done(); n += 1
            C.jitter(pace.get("between_hotels", [2.2, 4.8]))
            if cfg.get("long_rest_every") and n % int(cfg["long_rest_every"]) == 0:
                C.log("分批长休息..."); C.jitter(pace.get("long_rest", [25, 55]))
    finally:
        sp.close(); sr.close(); sn.close()
    if cfg.get("write_xlsx", True): write_xlsx(out_dir)
    C.log("全档案采集完成 %d 家 -> %s" % (n, out_dir))
    return 0
