# 排障

## 1. `permission_denied: This action requires the context returned by the latest cooperate sync`

bsk 0.4.0 对 `fill` / `click` / `evaluate` / `wheel` 强制协作协议。每个动作前必须：

```bash
bsk cooperate sync --session <SID> --settle --json   # 取 context_id
bsk evaluate "<expr>" --session <SID> --context <context_id> --json
```

- 返回里字段是 `context_id`（**不是** `context`）。
- 一个 `context_id` 只授权**一个**动作；动作后要重新 sync。
- 携程 `risk_Iframe_t_` 会抖动，常见 `The action's observed content changed` / `A page frame changed` / `ref @eN unknown` → 脚本已用 `--settle` + 最多 8 次重试 + `--depends-on` 吸收。
- **不要用 `@eN` ref 作长期选择器**（会变），用 CSS 选择器。

脚本的 `Bsk.action()` 已封装这套循环，不要绕过它直接调 `bsk evaluate`。

## 2. `sync` 报 `unexpected argument '--policy' found`

注入的 `bsk_session({action:"sync"})` 工具会传 `--policy auto`，CLI 0.4.0 不认（daemon 协议 1.7 / 扩展 1.8 版本错位）。**本技能全程走 CLI 子进程**，不用注入工具的 sync。

> 本节只针对 DSH 注入式工具；本仓库不依赖它，普通环境不会遇到。

## 3. `binding arguments must be lossless JSON`

注入工具参数里带了 `undefined`（如 `contextId: ctx || undefined`）。字段为 undefined 时**整个不传**。CLI 路径没这个问题。

## 4. daemon 起不来

DSH 宿主里 `bsk` 自动拉起 daemon 会失败：
`cannot start an independent Windows daemon; the host may prohibit Job Object breakaway` / `拒绝访问 (os error 5)`。

正解：先开一个后台任务常驻：
```bash
BSK_AUTO_START=0 bsk daemon start --foreground
```
确认 `BSK_AUTO_START=0 bsk status --json` 里 `browsers[].instance_id` 有值。所有客户端（含脚本）都带 `BSK_AUTO_START=0`。脚本已内置该环境变量。

普通终端里 `bsk` 通常会自动拉起 daemon，无需上面手工步骤；只有 DSH 桌面宿主这类禁止 Job Object breakaway 的环境才需要。

## 5. 抓不到价格 / `price_num` 全是 null

最常见：**没登录携程**。列表页显示「登录以查看会员价」，`room-price`/`price-line` 空。在真实 Edge/Chromium 里登录携程后重跑。交互运行会自动 `request-help`；后台定时加 `--no-handoff`，状态记 `needs_login`。

其次：携程改版，选择器失效。跑 `--calibrate <url>` 看 `calibration.json` 的 `class_hints`，调 `config/selectors.json`。

## 6. 抓到 `¥0 - ¥200` 这种假价格

`[class*=price]` 命中了左侧价格筛选栏 `.price-quick-choose`。`selectors.json` 已把 `room-price` / `price-line` 放前，并把 list 模式限定在 `.hotel-card` 内查找。若仍出现，改为更窄的类名。

## 7. 校准/批量跑很久

严格 `sync → 动作 → 再 sync` 每个动作都要往返，加上随机停顿，单目标约 20–60s 正常。`--calibrate` 曾因默认 120s 上限超时，用 `timeout 170 ...` 或更高上限即可。想快可临时把 `pace` 调小、`max_action_retries` 降到 4（不建议正式跑这么做）。

## 8. 黑窗

Windows 下脚本用 `subprocess.CREATE_NO_WINDOW` 起 bsk 子进程，不弹黑窗；**不要**再加 `DETACHED_PROCESS`（会让 worker 变无控制台，再拉 console 程序时 Win11 新建可见终端标签）。定时不限定平台：DSH 可用内置 `schedule`，其他环境用 cron / systemd timer / 任务计划程序等价触发。
