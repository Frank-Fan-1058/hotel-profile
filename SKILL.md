---
name: hotel-profile
description: 在本机真实已登录的 Edge/Chromium 里，用 bsk CLI（Tencent/BrowserSkill）模拟真人操作，批量采集酒店的价格与全档案信息（房型/床型/面积/会议室/泳池/健身房/餐厅/停车场/周边配套POI/地铁/酒店政策/简介等）。当用户要采集、监控、比价酒店价格，或要批量获取酒店设施与周边参数，或要配置定时批量取价时使用。具体站点地址与选择器集中在 config/settings.json 的 base_url 与 config/selectors.json，可替换，能力不绑定单一站点。抗反爬：复用真实登录态与浏览器指纹、只读渲染 DOM、拟人节奏、遇验证码或登录墙转人工。只强依赖独立开源的 bsk CLI，不依赖 DSH，可单独发布到 GitHub。
---

# 酒店数据采集（hotel-profile）

## 一句话结论

用**本机真实已登录的浏览器**（不是 requests / 不是 headless / 不是 Playwright 新开 profile）经 `bsk` CLI 逐页浏览，只读渲染后的 DOM，配拟人节奏。两种粒度：`list` 抓列表页最新价格快照，`profile` 抓单家详情页的全档案（房型、设施、周边、政策）。

## 依赖关系：只强依赖 bsk CLI，不依赖 DSH

**是**——核心驱动全靠 `bsk` CLI；**但**这是「外部命令行工具」级依赖（像 git / python），不是打包进本技能的组件，也不依赖 DSH 运行时、注入式 `bsk_*` 工具或任何 DSH 插件。

| 层 | 谁提供 | 随本仓库发布 |
| --- | --- | --- |
| 浏览器 + 目标站点登录态 | 用户自己的 Chrome/Edge | 否 |
| `bsk` CLI/daemon + 扩展 | [Tencent/BrowserSkill](https://github.com/Tencent/BrowserSkill)（独立开源） | 否，自行安装 |
| 目标站点页面渲染后 DOM | 目标站点 | 否 |
| 本技能：SOP、CSS 选择器、Python 驱动、配置模板 | 本仓库 | 是（MIT） |

把整个目录拷到任何装了 `bsk` 的机器，用 `python` 就能跑。详见 [[references/dependencies.md]]。

## 何时用

- 要批量看「对应酒店」的最新价格、评分、点评数、位置；
- 要更全的酒店信息：房型/床型/面积/楼层、会议室、泳池、健身房、餐厅、停车场、SPA、接送机、酒吧、周边配套 POI 与距离、地铁站、酒店政策、简介；
- 要定时重复取价形成价格快照/历史；
- 平台反爬强（当前默认 platform.com），直连 API 或 headless 会被拦，需要模拟真人行为。

## 前置条件（缺一不可）

1. **真实浏览器已登录目标平台账号**（当前默认 platform.com）：未登录时列表页只显示「登录以查看会员价」、价格为空。技能检测到会调 `request-help` 让真人登录。
2. **`bsk` CLI + 扩展 + daemon**：自行安装 [Tencent/BrowserSkill](https://github.com/Tencent/BrowserSkill)。
   - `bsk` 不在 PATH 时：设环境变量 `BSK_CLI`，或在 `config/settings.json` 写 `bsk_cli` 绝对路径。
   - 普通终端里 `bsk` 会自动拉起 daemon；**DSH 桌面宿主**禁止 Job Object breakaway，需手动常驻：`BSK_AUTO_START=0 bsk daemon start --foreground`，客户端同样带 `BSK_AUTO_START=0`（脚本已内置）。
3. **扩展已连浏览器**：`BSK_AUTO_START=0 bsk status --json` 能看到 `browsers[].instance_id`。断线时 `no_browser_connected`，等重连再跑。
4. **Python 3.9+**：生成 `.xlsx` 可选装 `openpyxl`（`pip install -r requirements.txt`）；不装也照常输出 CSV/JSONL。

## 红线（抗反爬的核心，别破坏）

| 做 | 不做 |
| --- | --- |
| 复用真实已登录 profile、真实 TLS/HTTP2 指纹 | 不 headless、不新开干净 profile 硬闯 |
| 只读渲染后 DOM（真人看到的内容） | 不重放 XHR / 内部 API、不伪造签名、不导出 cookie |
| 串行、单标签、随机停顿/滚轮/停留/乱序/分批长休息 | 不并发、不固定间隔、不高频 |
| 遇滑块/验证码/登录墙 → `request-help` 交真人 | 不硬刚验证码、不改扩展 Automation 设置 |
| 增量写盘 + 断点续跑 | 不一次性内存里攒完再写 |

详见 [[references/anti-detection.md]]。

## 快速开始

```bash
cd hotel-profile
python -m pip install -r requirements.txt          # 可选，只为输出 xlsx
cp config/hotels.example.csv config/hotels.csv
cp config/hotels.profile.example.csv config/hotels.profile.csv

python scripts/verify_probe.py                     # 自检：bsk 连通 + 协作协议
python scripts/hotel_scraper.py --calibrate "{base_url}/hotels/list?city=2&checkin=2026/11/20&checkout=2026/11/21"
python scripts/hotel_scraper.py --mode list --limit 1
python scripts/hotel_scraper.py --mode profile --limit 10
python scripts/hotel_scraper.py --mode discover --from-list "<列表页URL>"
python -m unittest discover -s tests -v            # 离线解析测试，不需浏览器
```

Windows 没有 `python` 时用 `py -3` 或 Python 绝对路径。要作为 DSH 技能用，把整个目录放到 `~/.dsh/skills/hotel-profile/`。

## 命令

| 命令 | 作用 |
| --- | --- |
| `--probe` / `verify_probe.py` | bsk 连通 + `cooperate sync` 协议自检 |
| `--calibrate <url>` | 打开真实页面，导出 class 名/价格文本/正文，用于校准选择器 |
| `--mode list` | 城市列表页：一次抓整页所有 `.hotel-card` 的价格与评分 |
| `--mode profile` / `--mode detail` | 逐家详情页全档案：房型、设施、周边、政策、基本信息 |
| `--mode discover --from-list URL` | 从列表页提取 hotelId 清单 → `output/discovered_hotels.csv` |
| `--from-list URL`（配 profile） | 先发现 hotelId 再直接逐家取全档案 |
| `--limit N` | 本次最多处理 N 个目标 |
| `--no-handoff` | 遇登录/验证码只记 `needs_login`/`blocked`，不弹人工 |
| `--settings <file>` | 指定别的配置文件 |

## 输入

- **list 模式**：`config/hotels.csv`，列 `hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note`。给 `url` 原样打开；只给 `city_id` 按 `list_url_template` 拼列表页。
- **profile/detail 模式**：`config/hotels.profile.csv`（同列，**必须填 hotel_id 或 detail url**）。实测 `city=2` → 上海。
- 首次使用把 `*.example.csv` 复制成真实清单；真实清单已被 `.gitignore` 排除，不会误提交。缺清单时脚本自动回退到 example 模板。
- 本机私有覆盖：`config/settings.local.json`（只写要覆盖的字段，如 `output_dir` 绝对路径），不发布。
- **hotelId 从哪来**：列表页 `.hotel-card` 的 `id` 属性（如 10000001）；或用 `--mode discover` 自动发现。

## 输出（默认 ./output，相对仓库根）

**价格快照（list）**
- `prices.csv` / `.jsonl` / `.xlsx` — 追加写，一行一条（一页多行）
- `progress.json` — 已完成 key，断点续跑

**全档案（profile）**
- `hotel_profiles.csv` — 一家一行：基本信息 + 设施布尔标记 + 周边汇总 + 政策 + 简介
- `hotel_rooms.csv` — 一个房型一行：房型名/床型/面积/楼层/窗/烟/WiFi/价/早餐/取消/余量
- `hotel_nearby.csv` — 一个周边 POI 一行：类别/名称/距离
- `hotel_report.xlsx` — 上面三张表各一个 sheet（带筛选与冻结表头）
- `progress_profile.json` / `discovered_hotels.csv` / `calibration.json`

字段口径见 [[references/data-schema.md]]。`status`：`ok` / `partial` / `needs_login` / `blocked` / `failed` / `error`。

## 选择器校准（重要）

`config/selectors.json` 的类名来自 **2026-11-15 真实登录态实测**（见 [[references/platform-page-map.md]]），不是保证。目标站点改版后：

1. 跑 `--calibrate <真实URL>`；
2. 看 `output/calibration.json` 的 `class_hints`；
3. 微调 `selectors.json` 中对应字段的候选 CSS（按优先顺序）；
4. 重跑 `--limit 1` 验证。

⚠️ 价格用 `.room-price .sale`（成交价）/ `.delete`（原价），不要用宽泛 `[class*=price]`（会命中左侧 `¥0-¥200` 筛选栏）。设施标记（会议室/泳池等）由 `has_*` 列给出，依据设施文本里的真实关键词，没有就写「否」，不臆测。

## 定时（可选）

- DSH：内置 `schedule` 建周期任务，prompt 指向 `--no-handoff`，避免无人值守卡在等人工。
- 其他环境：cron / systemd timer / Windows 任务计划程序等价触发即可。
- Windows 下脚本用 `CREATE_NO_WINDOW` 起 bsk 子进程，不弹黑窗。

## 发布到 GitHub

本仓库已备好 `LICENSE`(MIT)、`.gitignore`、`requirements.txt`、离线测试与无个人路径的默认配置。提交前跑 `python -m unittest discover -s tests -v` 与 `python scripts/verify_probe.py`，再 `git init && git add . && git commit` 后 push。BrowserSkill 的许可证以其仓库为准，本仓库不分发其二进制或源码。详见 [[references/dependencies.md]]。

## 排障

见 [[references/troubleshooting.md]]。最常见：daemon 没起、扩展断线（`no_browser_connected`）、`cooperate sync` 的 `context_id` 字段名、未登录导致无价格。

## 文件结构

```
hotel-profile/
├─ SKILL.md                 # Agent 入口（本文件）
├─ README.md                # GitHub / 用户速查
├─ LICENSE                  # MIT
├─ .gitignore               # 排除本机私有配置与运行产物
├─ requirements.txt         # 可选：openpyxl
├─ tests/test_parsers.py    # 离线解析测试（不需浏览器）
├─ references/
│  ├─ dependencies.md      # 依赖关系 / 移植 / 发布
│  ├─ anti-detection.md    # 拟人化 / 红线
│  ├─ platform-page-map.md    # 实测 URL 与 CSS 类（列表页 + 详情页）
│  ├─ data-schema.md       # 字段口径（价格快照 + 全档案三张表）
│  └─ troubleshooting.md   # bsk / 协作协议 / 登录墙
├─ scripts/
│  ├─ hotel_scraper.py       # 主驱动（list / 自检 / 校准 / 路由 profile）
│  ├─ hotel_profile.py     # 全档案采集（profile / discover）
│  ├─ profile_extract.js   # 详情页 DOM 抽取表达式
│  └─ verify_probe.py      # 自检入口
└─ config/
   ├─ settings.json              # 可发布默认值（无个人路径）
   ├─ settings.local.json        # 本机私有覆盖（不发布）
   ├─ selectors.json             # 字段 -> CSS 候选
   ├─ hotels.example.csv         # list 输入模板
   ├─ hotels.profile.example.csv # profile 输入模板
   ├─ hotels.csv                 # 本机真实清单（不发布）
   └─ hotels.profile.csv         # 本机真实清单（不发布）
```
