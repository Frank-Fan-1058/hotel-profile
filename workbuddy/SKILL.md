---
name: hotel-profile
display_name: 酒店价格与全档案采集
display_name_en: Hotel Price & Profile Collector
description: 批量采集酒店最新价格、评分、点评数、房型、会议室/泳池/健身房等设施、周边配套与政策。支持用户导入 Excel/CSV 酒店名单（名称可模糊匹配）。当用户要查价、比价、监控酒店价格，或整理酒店设施与周边参数清单，或给出一批酒店的价格档案对比表时使用。触发词：酒店价格、酒店比价、酒店信息采集、酒店设施、周边配套、酒店档案、批量查酒店、酒店名单。
description_zh: 通过用户真实已登录的浏览器批量采集酒店价格与全档案（房型、设施、周边配套、政策、简介），支持导入 Excel 名单并模糊匹配，输出 CSV / JSONL / Excel，可断点续跑。
description_en: Collect hotel prices and full profiles (rooms, facilities, nearby POIs, policies) through the user's real logged-in browser. Supports Excel/CSV name lists with fuzzy matching. Outputs CSV / JSONL / Excel with resume support.
examples_zh:
- "帮我查这 5 家酒店 11 月 20 日的价格和房型"
- "我有一份酒店名单 Excel，帮我把每家的会议室、泳池、健身房整理成一张表"
- "每天早上跑一次这 20 家酒店的房价，看看有没有降价"
examples_en:
- "Get prices and room types for these 5 hotels on Nov 20"
- "I have an Excel list of hotels — build one table of meeting room, pool and gym availability"
- "Run a daily price check on these 20 hotels and flag any drops"
version: 1.0.1
author: "Frank-Fan-1058"
allowed-tools: Bash, Read, Write, Edit
---

# 酒店价格与全档案采集

## 何时使用

- 一批酒店的**最新价格**（成交价、划线原价、评分、点评数）
- 酒店的**全档案**：房型（床型/面积/楼层/窗/早餐/取消政策/余量）、设施（会议室、泳池、健身房、餐厅、停车场、SPA、接送机、WiFi、酒吧）、周边配套（地铁站、地标、购物、休闲娱乐及距离）、政策与简介
- 多家酒店的**价格与档案对比表 / Excel**
- 用户给的是**名称清单**（Excel/CSV，名字未必与站点完全一致）→ 先做名称匹配再采集

## 第 0 步：环境自检（必须先做，别跳）

```bash
bsk status --json
```

按结果分三种情况处理：

| 结果 | 含义 | 处理 |
| --- | --- | --- |
| 有 `browsers[].instance_id` | 扩展已连上 | 进入第 1 步 |
| `browsers` 为空数组 | 扩展没装或没连上 | 按 @references/install-browser-extension.md 引导安装 |
| 命令不存在 | `bsk` CLI 未安装 | 同上，先装 CLI 再装扩展 |

**引导安装前必须先问清两件事**：用户的**操作系统**（Windows / macOS / Linux）和**浏览器**（Chrome / Edge / 其它 Chromium）。只给用户对应那一套步骤，不要把所有平台一起贴。

话术结构（别堆技术细节）：

> 这个技能要借用你浏览器里已登录的页面取数，需要装一个浏览器扩展做桥接。
> 你是 {系统} + {浏览器}，按三步做：①装 CLI（一条命令）②浏览器扩展管理页开「开发者模式」→「加载已解压的扩展程序」选目录 ③点一下扩展图标看到 connected。
> 装好告诉我，我继续。如果这台电脑装不了（公司管控），我可以只给你操作步骤自己跑。

分平台命令、扩展加载步骤、失败对照表见 @references/install-browser-extension.md。

### 还要确认登录态

让用户在**同一个浏览器**手动打开目标站点，确认右上角是用户名/会员等级（不是「登录/注册」），价格区显示真实价格而不是「登录以查看会员价」。

未登录时价格必为空白、状态记 `needs_login`——这是前置没满足，不是 bug。**不要**在未确认登录态时开始批量采集。

## 第 1 步：确认输入

问清目标站点、城市、入住/离店日期、酒店清单。清单三种形态按序优先：

1. **用户给了 Excel / CSV 名单**（常见，名称可能是俗称）→ 走第 2 步匹配
2. **用户给了 hotel_id** → 直接写入 `scripts/config/hotels.profile.csv`
3. **用户只给了城市** → 用列表页整页快照（`--mode list`）或 `--from-list` 自动发现

清单列：`hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note`

## 第 2 步：名称模糊匹配（用户导入 Excel 时）

用户名单常是「如家上海南京东路店」，站点上是「如家酒店(南京东路步行街店)」。**不要按名字硬找，先匹配成 ID**。

```bash
python scripts/hotel_scraper.py --mode match --input "用户名单.xlsx" --base-url "<站点根地址>" --limit 50
```

- 自动识别名称列（表头含「酒店 / 名称 / hotel / name / 门店」）；识别错了用 `--name-column "列名"` 指定
- 支持 `.xlsx` 与 `.csv`；xlsx 需 `openpyxl`
- 匹配分三档，**绝不硬猜**：

| 情况 | 输出 |
| --- | --- |
| 分数达标且领先第二名足够多 | 写入 `output/matched_hotels.csv`，可直接采集 |
| 分数够但候选接近（同品牌不同分店） | 进 `output/match_review.csv` 待人工确认 |
| 分数低于阈值 | 同上，并列前三个候选供选择 |

- 用户名称里的**地点/分店词**（「武宁路」「金桥」）会加权，用来区分同品牌不同门店
- 通用词（酒店/宾馆/分店/店…）不参与打分，避免靠这些词虚高

**给用户的话术**：把 `match_review.csv` 待确认项原样列给用户（原名 + 前三个候选 + 分数），让用户选，不要替用户认定。

匹配完成后复制成清单：

```bash
cp output/matched_hotels.csv scripts/config/hotels.profile.csv
```

## 第 3 步：跑采集

```bash
python scripts/verify_probe.py
python scripts/hotel_scraper.py --mode profile --limit 10
python scripts/hotel_scraper.py --mode list --limit 1
python scripts/hotel_scraper.py --mode profile --from-list "<列表页URL>" --limit 10
```

无人值守加 `--no-handoff`：遇登录墙/验证码只记状态不阻塞。

单次 10–20 家以内；更多分批。不要并发、不要缩短等待。

## 第 4 步：读结果并交付

输出在 `output/`：

| 文件 | 内容 |
| --- | --- |
| `prices.csv / .jsonl / .xlsx` | 列表页价格快照，追加写 |
| `hotel_profiles.csv` | 一家一行：基本信息 + 9 项设施标记 + 周边汇总 + 政策 + 简介 |
| `hotel_rooms.csv` | 一个房型一行：床型/面积/楼层/窗/烟/WiFi/价/早餐/取消/余量 |
| `hotel_nearby.csv` | 一个 POI 一行：类别/名称/距离 |
| `hotel_report.xlsx` | 上面三张表各一个 sheet |
| `matched_hotels.csv / match_review.csv` | 名称匹配成功 / 待确认 |

回复用户时：先说结论（成功几家、价格区间）再给表；表格只放用户要的字段；**必须说明**设施标记按页面文本判定，页面没写记「否」，不代表一定没有；失败的要列名字和原因，不要掩盖。

## 硬性约束

**必须**：复用用户真实已登录浏览器；串行、单标签、随机停顿、滚动、分批休息；只读渲染后内容；增量写盘 + 断点续跑；遇验证码/登录墙交真人。

**禁止**：headless、新开干净 profile、改 UA、导 cookie；重放内部接口、伪造签名；并发提速、高频轮询、绕验证码；**编数据**（没抓到就 null / 「未找到」）。

## 页面改版怎么办

结果 0 行或字段大量为空 → 选择器变了：

```bash
python scripts/hotel_scraper.py --calibrate "<真实页面URL>"
```

看 `output/calibration.json` 的 `class_hints`，调 `scripts/config/selectors.json` 候选 CSS，再 `--limit 1` 验证。价格务必用 `.room-price .sale`（成交价）/ `.delete`（原价），**不要**用宽泛的 `[class*=price]`（会命中左侧筛选栏）。

## 排障

| 现象 | 处理 |
| --- | --- |
| `no_browser_connected` | 扩展断线，按 install 文档让用户重连 |
| 价格全空、`needs_login` | 用户没登录，请其登录后重跑 |
| `retry_exhausted` | 页面风控抖动，已每家用独立会话 + 重试；仍失败跳过并记 `error` |
| Excel 没生成 | 缺 `openpyxl`，`pip install openpyxl`；CSV 不受影响 |
| 名称匹配全落 review | 用户名称与站点差异大或候选池太小（加大 `pool_rounds`） |

## 参考

- @references/install-browser-extension.md — 分平台 CLI 与扩展安装、失败对照
- @references/data-schema.md — 字段口径
- @references/anti-detection.md — 拟人节奏与红线
- @references/platform-page-map.md — 实测选择器
