# 依赖关系说明（发布 / 移植必读）

## 结论

**只有一个强依赖：`bsk` CLI（Tencent/BrowserSkill）＋ 它的浏览器扩展 ＋ 一个已登录携程的 Chromium/Edge。**

本技能**不是 DSH 插件**，不依赖 DSH 运行时、不依赖注入式 `bsk_*` 工具、不打包 BrowserSkill 本体。它只是「Agent Skill（`SKILL.md`）＋ 一层薄 Python 驱动」，通过**命令行**调用 `bsk`。把整个目录拷到任何装有 `bsk` 的机器，用 `python` 就能跑。

## 分层

| 层 | 谁提供 | 随本仓库发布 |
| --- | --- | --- |
| 浏览器：真实 profile / 登录态 / TLS 指纹 / 扩展列表 | 用户自己的 Chrome/Edge | 否 |
| BrowserSkill 扩展 + `bsk` CLI + daemon | [Tencent/BrowserSkill](https://github.com/Tencent/BrowserSkill)（独立开源项目） | 否，用户自行安装 |
| 携程页面（列表页 / 详情页渲染后 DOM） | 携程 | 否 |
| 本技能：SOP、CSS 选择器、Python 驱动、配置模板 | 本仓库 | 是（MIT） |

## 用到的 bsk 命令面

只依赖 CLI 子命令，不碰内部协议字段：

- `session start --no-focus --json` / `session stop <SID> --json`
- `navigate <url> --session <SID> --wait-until domcontentloaded --json`
- `cooperate sync --session <SID> --settle --max-tokens 700 --json` → 取 `context_id`
- `evaluate <expr> --session <SID> --context <CTX> --json`
- `wheel --delta-y N ...`、`request-help --prompt ... --json`
- `status --json`（排障时人工用）

「每个动作前重新 sync 取 `context_id`、一个 context 只授权一个动作」封装在 `Bsk.action()` 里，并对 `synchronize / frame changed / content changed` 做有限重试。脚本用 `BSK_AUTO_START=0`，避免客户端自行拉起 daemon。

## 版本兼容

- 实测：bsk 0.4.0，daemon 协议 1.7 / 扩展 1.8（存在 version skew，不影响 CLI 路径）。
- 携程页面注入 `risk_Iframe_t_` 风控 iframe 会让 `@eN` ref 抖动，所以脚本**只用 CSS 选择器**，不用 ref。
- 上游改 CLI 参数：先跑 `--probe` 定位；页面改版：跑 `--calibrate` 看 `class_hints` 再调 `selectors.json`。

## 可选依赖

- `openpyxl`：仅生成 `.xlsx` 时用；缺失时 CSV/JSONL 照常输出，日志提示跳过 Excel。

## 不依赖什么

- DSH / `~/.dsh` / 任何 DSH 插件或注入工具
- Playwright / Selenium / requests / curl 直连携程接口
- 账号密码、cookie 导出、签名伪造、验证码绕过、headless
- 任何携程内部 JSON API（只读渲染后 DOM）

## 与 DSH 有关的两处（可选，不影响移植）

1. `SKILL.md` 的 frontmatter 是 Agent Skill 发现格式；没有 DSH 时它只是一份说明文档，脚本照跑。
2. 定时运行：DSH 可用内置 `schedule` 并加 `--no-handoff`；其他环境用 cron / systemd timer / 任务计划程序等价触发。

## 许可与分发

本仓库代码 MIT。BrowserSkill 为独立项目，许可证以其仓库为准；本仓库不复制、不修改、不分发其二进制或源码，只在文档里链接其安装说明。

## 相关

- [[references/troubleshooting]]
- [[references/anti-detection]]
- 技能入口：[[SKILL]]
