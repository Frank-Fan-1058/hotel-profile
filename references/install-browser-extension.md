# 浏览器扩展安装引导（首次使用必读）

本技能不直连网站接口，而是复用**用户自己浏览器里已登录的页面**，因此需要一个浏览器扩展作为桥。
下面的检查与引导要**在开始采集前完成**，不要等跑到一半才报错。

## 第 0 步：先检查，别假设

```bash
bsk status --json
```

看返回里的 `browsers`：

- 数组**非空**且含 `instance_id` → 已就绪，跳到「第 3 步」。
- 数组为空 → 扩展没装或没连上，继续第 1 步。
- 命令本身找不到（`command not found`）→ `bsk` CLI 都没装，先装 CLI（见 references/dependencies.md）。

## 第 1 步：装 CLI（`bsk`）

按用户的操作系统给对应命令。**先问清系统和浏览器再给命令**，不要一股脑全贴。

| 系统 | 安装方式 |
| --- | --- |
| Windows | 从项目 Releases 下载 `bsk-x86_64-pc-windows-msvc.zip⟧ 解压，把 `bsk.exe` 放进 PATH 里的目录（如 `%LOCALAPPDATA%\\Programs\\bsk⟧），或设环境变量 `BSK_CLI⟧ 指向它 |
| macOS | Releases 下载 `bsk-aarch64-apple-darwin.tar.gz⟧（Apple 芯片）或 `x86_64⟧（Intel），解压后 `chmod +x bsk⟧ 再移入 `/usr/local/bin/⟧ |
| Linux | Releases 下载对应 `bsk-*-unknown-linux-gnu.tar.gz⟧，解压后 `install -m755 bsk /usr/local/bin/⟧ |

装完验证：```bash
bsk --version
```
能打印版本号即可。

## 第 2 步：装浏览器扩展

1. 打开 `https://github.com/Tencent/BrowserSkill⟧ 的 Releases，下载 `browser-skill-extension-*.zip⟧。
2. 解压到一个**固定目录**（如 `~/browser-skill-extension⟧），不要放在下载目录里随手删。
3. 在目标浏览器地址栏打开扩展管理页：

   | 浏览器 | 地址 |
   | --- | --- |
   | Chrome / Edge / Brave / 其它 Chromium | `chrome://extensions⟧ 或 `edge://extensions⟧ |
   | Firefox | 不支持（本技能依赖 Chromium 扩展） |

4. 打开右上角「开发者模式」→ 点「加载已解压的扩展程序」→ 选择第 2 步解压出来的目录。
5. 扩展图标出现后**点一下**，弹窗里应显示 `connected⟧。

**常见失败**

| 现象 | 原因与处理 |
| --- | --- |
| 加载时提示清单文件缺失 | 选错了目录层级，要选**包含 `manifest.json⟧ 的那一层** |
| 扩展装了但 `bsk status⟧ 仍是空数组 | 扩展弹窗没点开过 / 浏览器重启过；点一下扩展图标等它显示 connected |
| 公司电脑禁用开发者模式 | 无法装，请用户换个人设备，或放弃本方案 |

## 第 3 步：确认登录态

在**同一个浏览器**里手动打开目标站点并确认已登录。判断方法：

- 页面右上角显示用户名 / 会员等级（不是「登录 / 注册」）
- 价格区显示真实价格，而不是「登录以查看会员价」

未登录时本技能抓到的价格会是空的，状态记为 `needs_login`——这不是 bug，是前置没满足。

## 第 4 步：跑自检

```bash
bsk status --json          # 应看到 browsers[].instance_id
python scripts/verify_probe.py
```

自检输出 `结果: OK` 才算环境就绪，可以开始采集。

## 给用户的话术模板

首次使用、且检测到扩展未连接时，按这个结构说明，**不要堆技术细节**：

> 这个技能需要借用你浏览器里已登录的页面来取数，所以要装一个浏览器扩展做桥接。
> 你现在用的是 {系统} + {浏览器}，按这三步做：{三步}。装完点一下扩展图标，看到 connected 就行。
> 装好告诉我，我再继续。如果你这台电脑装不了（比如公司管控），我可以改为只给你操作步骤，你自己跑。

## 不要做的事

- 不要让用户在**无痕/隐私窗口**里装扩展后就用——很多扩展在无痕下默认不启用。
- 不要建议用户关闭浏览器安全设置、关闭开发者模式警告、或用管理员权限强装。
- 不要在未确认登录态的情况下就开始批量采集，白跑一趟还浪费配额。
