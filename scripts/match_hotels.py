# -*- coding: utf-8 -*-
"""
酒店名称模糊匹配：用户导入的 Excel 清单里常是「俗称 / 简称 / 带分店备注」的名字，
和目标站点上的正式名称不完全一致。本模块负责把它们对齐成可采集的酒店 ID。

流程：
  1) 归一化用户名称（去括号备注、去通用后缀、全半角统一、去标点）
  2) 用名称到站点搜索 / 列表页取候选（名称 + ID）
  3) 字符二元组相似度 + 关键词覆盖 + 包含关系打分
  4) 高于阈值 → 采用；低于阈值 → 记候选前三名，交人工确认，不硬猜

用法：
  python scripts/hotel_scraper.py --mode match --input 酒店清单.xlsx --city-id 2
  python scripts/hotel_scraper.py --mode match --input 酒店清单.xlsx --name-column 酒店名称 --limit 10
"""
from __future__ import annotations
import os, sys, re, csv, json, unicodedata, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hotel_scraper as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 通用词：不参与区分度计算，避免「酒店 / 分店」这类词把相似度抬高
NOISE = [
    "大酒店", "酒店", "宾馆", "饭店", "旅馆", "公寓", "民宿", "客栈", "度假村", "度假酒店",
    "旗舰店", "分店", "店", "有限公司", "集团", "连锁",
    "hotel", "inn", "hostel", "resort", "apartment", "the",
]
# 常见同义/缩写归一
ALIAS = {
    "如家": "如家", "汉庭": "汉庭", "锦江": "锦江", "亚朵": "亚朵",
    "希尔顿": "希尔顿", "万豪": "万豪", "洲际": "洲际", "凯悦": "凯悦",
    "全季": "全季", "桔子": "桔子", "维也纳": "维也纳",
}

POOL_JS = r"""(function(){
  var out = {}, n = 0;
  var cards = document.querySelectorAll('.hotel-card,[class*=hotelCard],[class*=hotel-card]');
  Array.prototype.forEach.call(cards, function(c){
    var id = (c.id || c.getAttribute('data-hotel-id') || '').trim();
    var ne = c.querySelector('[class*=hotelName],[class*=hotel-title],h3,h2');
    var name = ne ? (ne.innerText || '').replace(/\s+/g, ' ').trim() : '';
    name = name.replace(/\s*广告\s*$/, '').trim();
    if (/^[0-9]{4,12}$/.test(id) && name) { out[id] = name.slice(0, 80); }
    n++;
  });
  return { cards: n, map: out, scrollY: Math.round(window.scrollY),
           docH: document.body ? document.body.scrollHeight : 0 };
})()"""


# ----------------------------- 纯函数（可离线测试） -----------------------------
def normalize(name):
    """归一化：全半角统一 → 去括号备注 → 去标点 → 去通用后缀 → 小写。"""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name)).strip().lower()
    s = re.sub(r"[（(【\[].{0,40}?[)）】\]]", " ", s)   # 括号备注
    s = re.sub(r"[\s\-_·・,，.。/\\|+&*#@!?？：:；;'\"“”‘’]+", " ", s)
    s = re.sub(r"\s+", "", s)
    for w in NOISE:
        s = s.replace(w, "")
    return s


def bigrams(s):
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def tokens(s):
    """把名称切成有区分度的片段：去掉通用词后的连续中文/字母数字块。"""
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[（(【\[].{0,40}?[)）】\]]", " ", s)
    s = re.sub(r"[\s\-_·・,，.。/\\|+&*#@!?？：:；;'\"“”‘’]+", " ", s)
    out = []
    for seg in s.split():
        for w in NOISE:
            seg = seg.replace(w, " ")
        for part in seg.split():
            if len(part) >= 2:
                out.append(part)
    return out


def token_bonus(query, cand):
    """用户名称里独有的地点/分店词，命中候选就加权。

    例：用户写「云和夜泊 武宁路店」，候选有「(武宁路环球港店)」和「(浦东机场店)」，
    「武宁路」只命中前者 → 用它打破同品牌歧义。
    """
    q, c = tokens(query), tokens(cand)
    if not q or not c:
        return 0.0
    hit = 0
    for t in q:
        if any(t in x or x in t for x in c):
            hit += 1
    return 0.12 * hit if hit else 0.0


def similarity(a, b):
    """0~1。字符二元组 Dice 为主，叠加包含关系与独有词命中加成。"""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    A, B = bigrams(na), bigrams(nb)
    dice = 2 * len(A & B) / (len(A) + len(B)) if (A and B) else 0.0
    # 一方完整包含另一方（常见：简称 vs 全称）→ 至少 0.85
    contain = 0.85 if (na in nb or nb in na) else 0.0
    # 首字相同（中文品牌名强特征）给一点加成
    head = 0.05 if na[0] == nb[0] else 0.0
    return min(1.0, max(dice, contain) + head + token_bonus(a, b))


def pick_best(query, candidates, threshold=0.72, top_k=3):
    """从候选里挑最匹配的。返回 (best, ranked)。

    best 为 None 表示置信度不足，调用方应转人工而非硬猜。
    """
    ranked = []
    for c in candidates or []:
        s = similarity(query, c.get("name") or "")
        ranked.append({"id": c.get("id") or "", "name": c.get("name") or "",
                       "score": round(s, 4)})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    top = ranked[:top_k]
    if not top or top[0]["score"] < threshold:
        return None, top
    # 第一名与第二名差距过小 → 存在歧义，也交人工
    if len(top) > 1 and top[0]["score"] - top[1]["score"] < 0.05 and top[0]["score"] < 0.92:
        return None, top
    return top[0], top


def search_candidates(cfg, keyword, city_id=None):
    """兜底：拿不到候选池时，按名称打开列表页取当屏卡片。"""
    url = list_url(cfg, city_id)
    b = C.Bsk(cfg.get("bsk_cli"), cfg)
    b.start(cfg.get("browser_instance") or None)
    try:
        b.navigate(url)
        C.jitter([2.5, 4.0])
        for dy in (400, 600):
            b.wheel(dy); C.jitter([0.8, 1.3])
        r = b.evaluate(POOL_JS)
        v = r.get("value") if isinstance(r.get("value"), dict) else {}
        return [{"id": k, "name": nm} for k, nm in (v.get("map") or {}).items()]
    finally:
        b.stop()


# ----------------------------- IO -----------------------------
def read_input_rows(path, name_column=None, city_column=None, limit=0):
    """读 csv / xlsx，返回 [{raw_name, city}]。"""
    ext = os.path.splitext(path)[1].lower()
    rows = []
    if ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise RuntimeError("读取 xlsx 需要 openpyxl：pip install openpyxl")
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        data = list(ws.iter_rows(values_only=True))
        if not data:
            return []
        header = [str(x).strip() if x is not None else "" for x in data[0]]
        idx = None
        if name_column:
            idx = header.index(name_column) if name_column in header else None
        if idx is None:
            for i, h in enumerate(header):
                if any(k in h for k in ("酒店", "名称", "hotel", "name", "门店")):
                    idx = i
                    break
        if idx is None:
            idx = 0
        city_idx = None
        for i, h in enumerate(header):
            if any(k in h for k in ("城市", "city")):
                city_idx = i
                break
        for r in data[1:]:
            v = r[idx] if idx < len(r) else None
            if v is None or str(v).strip() == "":
                continue
            city = (str(r[city_idx]).strip() if city_idx is not None and city_idx < len(r) and r[city_idx] else "")
            rows.append({"raw_name": str(v).strip(), "city": city})
    else:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return []
            key = name_column if name_column in (reader.fieldnames or []) else None
            if not key:
                for h in reader.fieldnames:
                    if any(k in h for k in ("酒店", "名称", "hotel", "name", "门店")):
                        key = h
                        break
            key = key or reader.fieldnames[0]
            city_key = next((h for h in reader.fieldnames if any(k in h for k in ("城市", "city"))), None)
            for r in reader:
                v = (r.get(key) or "").strip()
                if v:
                    rows.append({"raw_name": v, "city": (r.get(city_key) or "").strip() if city_key else ""})
    if limit:
        rows = rows[:int(limit)]
    return rows


def list_url(cfg, city_id=None):
    base = (cfg.get("base_url") or "").rstrip("/")
    tpl = cfg.get("list_url_template") or "{base_url}/hotels/list?city={city_id}&checkin={checkin}&checkout={checkout}"
    return (tpl.replace("{base_url}", base)
               .replace("{city_id}", str(city_id or cfg.get("default_city_id") or ""))
               .replace("{checkin}", C.fmt_date(cfg.get("checkin"), cfg))
               .replace("{checkout}", C.fmt_date(cfg.get("checkout"), cfg)))


def collect_pool(cfg, city_id=None, rounds=12, per_round_pause=(2.0, 3.0)):
    """滚动城市列表页，累积 酒店ID -> 名称 候选池。

    列表页的卡片自带 id 属性与名称，一条条滚动比调站内搜索接口更稳、也更像真人浏览。
    """
    url = list_url(cfg, city_id)
    b = C.Bsk(cfg.get("bsk_cli"), cfg)
    b.start(cfg.get("browser_instance") or None)
    pool = {}
    try:
        C.log("  打开城市列表:", url)
        b.navigate(url)
        C.jitter([3.2, 4.2])
        for i in range(int(rounds)):
            r, v = {}, {}
            # 页面风控抖动时 evaluate 可能整体失败（code=retry_exhausted），重取几次再判空
            for attempt in range(3):
                r = b.evaluate(POOL_JS)
                v = r.get("value") if isinstance(r.get("value"), dict) else {}
                if v.get("map"):
                    break
                if r.get("code"):
                    C.log("    取候选失败(%s)，重试 %d/3" % (r.get("code"), attempt + 1))
                    C.jitter([1.5, 2.5])
            m = v.get("map") or {}
            before = len(pool)
            pool.update(m)
            C.log("  第 %d 屏：卡片 %s，累计 %d 家" % (i + 1, v.get("cards"), len(pool)))
            if i >= 3 and len(pool) == before:
                stalled = getattr(collect_pool, "_stall", 0) + 1
                collect_pool._stall = stalled
                if stalled >= 2:
                    break
            else:
                collect_pool._stall = 0
            b.wheel(1500)
            C.jitter(list(per_round_pause))
    finally:
        b.stop()
    return pool


def run_match(cfg, sel, a):
    out_dir = C.output_dir(cfg)
    os.makedirs(out_dir, exist_ok=True)
    src_path = a.input
    if not src_path or not os.path.exists(src_path):
        C.log("请用 --input 指定酒店清单（csv / xlsx）")
        return 1

    rows = read_input_rows(src_path, a.name_column, None, a.limit or 0)
    if not rows:
        C.log("清单为空，或没找到名称列（可用 --name-column 指定）")
        return 1
    C.log("读入", len(rows), "个酒店名称")

    threshold = float(cfg.get("match_threshold", 0.72))
    limit = a.limit or len(rows)
    out_rows, review_rows = [], []
    seen_kw = {}

    # 候选池：滚动城市列表页累积「ID -> 名称」，比逐个调站内搜索更稳
    pool = {}
    if not a.no_pool:
        try:
            pool = collect_pool(cfg, cfg.get("default_city_id"), rounds=int(cfg.get("pool_rounds", 8)))
        except Exception as e:
            C.log("候选池收集失败，改用逐个搜索:", repr(e))
    cands_all = [{"id": k, "name": v} for k, v in pool.items()]

    for i, row in enumerate(rows[:limit], 1):
        name = row["raw_name"]
        city_id = row.get("city_id") or cfg.get("default_city_id")
        C.log("(%d/%d) 匹配: %s" % (i, min(limit, len(rows)), name))
        try:
            cands = cands_all
            if not cands:
                cands = search_candidates(cfg, normalize(name) or name, city_id)
            best, top = pick_best(name, cands, threshold)
        except Exception as e:
            C.log("  匹配失败:", repr(e))
            best, top, cands = None, [], []
        if best:
            out_rows.append({"hotel_id": best["id"], "url": "", "city_id": city_id or "",
                             "city": row.get("city") or cfg.get("default_city", ""),
                             "hotel_name": best["name"],
                             "checkin": cfg.get("checkin", ""), "checkout": cfg.get("checkout", ""),
                             "room_type": "", "note": "匹配度 %.2f｜原名 %s" % (best["score"], name)})
            C.log("  -> %s (%.2f)" % (best["name"], best["score"]))
        else:
            review_rows.append({"raw_name": name, "reason": "置信度不足或存在歧义",
                                "candidates": " / ".join("%s(%.2f)" % (c["name"], c["score"]) for c in top) or "无候选"})
            C.log("  -> 待人工确认 | 候选:", review_rows[-1]["candidates"][:80])

    p_out = os.path.join(out_dir, "matched_hotels.csv")
    with open(p_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "url", "city_id", "city", "hotel_name",
                                          "checkin", "checkout", "room_type", "note"])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    p_rev = os.path.join(out_dir, "match_review.csv")
    with open(p_rev, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["raw_name", "reason", "candidates"])
        w.writeheader()
        for r in review_rows:
            w.writerow(r)

    C.log("匹配完成：成功 %d 家，待确认 %d 家" % (len(out_rows), len(review_rows)))
    C.log("已写入", p_out, "与", p_rev)
    if review_rows:
        C.log("提示：待确认的酒店请看 match_review.csv，人工选定后补进 matched_hotels.csv 再跑 --mode profile")
    return 0
