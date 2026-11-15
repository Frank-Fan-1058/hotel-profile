# 反爬策略：只做「真人会做的事」

目标站点的反爬不是单一 UA 校验，而是设备指纹 + 登录态 + 行为序列 + 风控 iframe 的组合。绕过的正解不是伪造，而是**本来就是真人**：用用户自己每天在用的浏览器、自己的账号、正常的浏览节奏。

## 六条硬红线

1. **真实 profile**：`bsk session start --no-focus` 开的是扩展挂在用户真实 Edge/Chromium 上的 Agent Window，共享登录态、cookie、TLS/HTTP2 指纹、扩展列表、屏幕尺寸。不新开干净 profile，不 headless。
2. **只读渲染 DOM**：`evaluate` / `snapshot` / `extract` 读的都是页面已经渲染出来、真人眼睛看到的内容。不重放页面内部 XHR、不调未公开的 JSON API、不伪造 `_fxpcqlniredot` 之类签名、不导出 cookie 给别的客户端。
3. **认证留在浏览器内**：脚本从不接触账号密码或 token。登录过期/滑块/短信验证 → `bsk request-help` 弹出 overlay 交真人，绝不尝试自动过验证。
4. **不改 Automation 设置**：扩展的 Automation / 协作策略由用户决定，脚本只按 `cooperate sync` 返回的 `context_id` 走合规动作，不去关安全开关。
5. **行为像人**：串行、单标签、随机间隔、滚轮、停留、乱序、分批长休息、每页限量、失败最多重试几次就跳过。
6. **增量落盘**：每抓完一个目标立即写 CSV/JSONL + 更新 `progress.json`，被中断也不丢，重跑自动跳过已完成。

## 拟人节奏参数（config/settings.json → pace）

| 参数 | 默认 | 含义 |
| --- | --- | --- |
| `after_navigate` | 1.5–3.2s | 导航后等页面渲染 |
| `dwell` | 1.0–2.6s | 提取前停留（像在看） |
| `between_hotels` | 2.2–4.8s | 两个目标之间 |
| `long_rest` / `long_rest_every` | 25–55s / 每 12 个 | 分批长休息 |
| `wheel_steps_max` | 2 | 每次随机滚 1–2 下 |
| `shuffle` | true | 打乱清单顺序 |
| `max_rows_per_page` | 60 | 单页最多取多少卡片 |
| `max_per_run` | 0（不限） | 单次运行上限 |

间隔用 `random.uniform`，不是固定 sleep。

## 风控触发时的行为

`blocked()` 检查正文里的 `登录以查看` / `立即登录` / `安全验证` / `请拖动` / `人机验证` / `访问验证` / `captcha` 等：

- **交互运行**（默认 `allow_handoff: true`）→ `request-help` 弹 overlay 请真人登录或过验证 → 等人完成 → 重新提取 → 仍失败则记 `needs_login`/`blocked`。
- **后台定时**（`--no-handoff`）→ 不阻塞，直接把该目标记为 `needs_login` 并继续下一个，留给下一轮（人登录后）补。

绝不：自动打码、反复刷新硬闯、并发多标签提速。

## 为什么不用 computer use 作主路径

`cua_driver_native__*` 纯视觉点击慢且脆，坐标随窗口/缩放漂移，不适合批量。只在极端的「DOM 里根本没有可点元素」时作兜底。主路径是 browser-skill 的 DOM 级动作（同样是真实浏览器事件）。
