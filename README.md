# ctrip-hotel-price

在本机**真实已登录**的 Chrome/Edge 里，用 [BrowserSkill (\`bsk\`)](https://github.com/Tencent/BrowserSkill) 模拟真人浏览，批量采集携程酒店的价格与全档案（房型、会议室/泳池等设施、周边配套、政策…）。只读渲染后 DOM，不 headless、不重放 API、不碰 cookie。

## 它跟 browser-skill 是什么关系

**强依赖，但只是外部命令行依赖**：核心动作全走 \`bsk\` CLI；本仓库不含也不分发 BrowserSkill 本体，不依赖 DSH 运行时或注入式 \`bsk_*\` 工具。把它当 \`git\` / \`python\` 一类的前置工具装好即可。详见 [references/dependencies.md](references/dependencies.md)。

| 层 | 谁提供 | 随本仓库发布 |
| --- | --- | --- |
| 浏览器 + 携程登录态 | 你自己的 Chrome/Edge | 否 |
| \`bsk\` CLI/daemon + 扩展 | Tencent/BrowserSkill | 否（自行安装） |
| 携程页面 DOM | 携程 | 否 |
| 本仓库：SOP / 选择器 / Python 驱动 / 配置模板 | 本仓库 | 是（MIT） |

## 前置

1. Python 3.9+（可选 \`pip install -r requirements.txt\`，仅用于输出 xlsx）
2. \`bsk\` 在 PATH（或设 \`BSK_CLI\` / \`config/settings.json\` 的 \`bsk_cli\` 绝对路径）＋ 浏览器扩展已连接
3. 真实浏览器里已登录携程账号（未登录看不到会员价）
4. daemon 可用：\`BSK_AUTO_START=0 bsk status --json\` 能看到 \`browsers[].instance_id\`。普通终端 \`bsk\` 会自动拉起；DSH 桌面宿主里需手动常驻 \`BSK_AUTO_START=0 bsk daemon start --foreground\`。

## 安装 / 运行

```bash
git clone <your-repo-url> && cd ctrip-hotel-price
python -m pip install -r requirements.txt
cp config/hotels.example.csv config/hotels.csv
cp config/hotels.profile.example.csv config/hotels.profile.csv

python scripts/verify_probe.py                 # 自检：bsk 连通 + 协作协议
python scripts/ctrip_hotel.py --mode list --limit 1
python scripts/ctrip_hotel.py --mode profile --limit 10
python scripts/ctrip_hotel.py --mode discover --from-list "<列表页URL>"
python -m unittest discover -s tests -v       # 离线解析测试，不需浏览器
```

要作为 DSH 技能使用：把整个目录放到 \`~/.dsh/skills/ctrip-hotel-price/\`。

## 配置

- \`config/settings.json\`：可发布的默认值（无个人路径）。\`bsk_cli\` 默认 \`"bsk"\` 走 PATH；\`output_dir\` 默认 \`"./output"\`（相对仓库根）。
- \`config/settings.local.json\`：本机私有覆盖（已被 \`.gitignore\` 排除）。例：\`{"output_dir": "D:/work/产出"}\`。
- \`config/selectors.json\`：字段 → CSS 候选；携程改版先 \`python scripts/ctrip_hotel.py --calibrate <url>\` 再调。

## 输出（默认 ./output）

| 模式 | 文件 | 内容 |
| --- | --- | --- |
| list | \`ctrip_prices.csv\` / \`.jsonl\` / \`.xlsx\` | 列表页价格快照（追加写，带时间戳） |
| profile | \`ctrip_profiles.csv\` | 一家一行：基本信息 + 9 项设施标记 + 周边/政策/简介 |
| profile | \`ctrip_rooms.csv\` | 一个房型一行：床型/面积/楼层/窗/烟/WiFi/价/早餐/取消/余量 |
| profile | \`ctrip_nearby.csv\` | 一个 POI 一行：类别/名称/距离 |
| profile | \`ctrip_hotel_full.xlsx\` | 上面三张表各一个 sheet |

口径见 [references/data-schema.md](references/data-schema.md)。「会议室/泳池」等标记只按页面文本关键词判定，页面没写就是「否」，不臆测。

## 抗反爬设计

复用真实 profile 的登录态与 TLS 指纹 → 只读渲染后 DOM → 串行单标签 + 随机停顿/滚轮/停留/乱序/长休息 → 遇验证码或登录墙 \`request-help\` 交真人（后台加 \`--no-handoff\` 只记状态）。不 headless、不改 UA、不导出 cookie、不伪造签名、不重放内部 API。详见 [references/anti-detection.md](references/anti-detection.md)。

## 定时（可选）

DSH：\`schedule_create\` + \`--no-handoff\`；其他环境：cron / systemd timer / 任务计划程序。Windows 下脚本用 \`CREATE_NO_WINDOW\` 起 bsk 子进程，不弹黑窗。

## 发布到 GitHub

本仓库已备好 \`LICENSE\`(MIT)、\`.gitignore\`、\`requirements.txt\`、离线测试与无个人路径的默认配置。提交前跑 \`python -m unittest discover -s tests -v\` 与 \`python scripts/verify_probe.py\`，再 \`git init && git add . && git commit\` 后 push。BrowserSkill 的许可证以其仓库为准，本仓库不分发其二进制或源码。

## 许可

MIT，见 [LICENSE](LICENSE)。
