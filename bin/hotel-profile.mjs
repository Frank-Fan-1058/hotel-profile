#!/usr/bin/env node
/**
 * hotel-profile CLI（npm 包入口）
 *
 * 只是 Python 驱动的薄包装：把参数原样转给 scripts/ctrip_hotel.py，
 * 并保证 cwd 落在包根目录，使 config/ 与 output/ 的相对路径生效。
 *
 * 用法：
 *   npx hotel-profile --mode list --limit 1
 *   npx hotel-profile --mode profile --limit 10
 *   npx hotel-profile --help
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { existsSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const script = join(root, "scripts", "ctrip_hotel.py");

const CANDIDATES = [
  process.env.HOTEL_PROFILE_PYTHON,
  process.env.PYTHON,
  "python3",
  "python",
  "py",
].filter(Boolean);

function pickPython() {
  for (const c of CANDIDATES) {
    if (c.includes("/") || c.includes("\\")) {
      if (existsSync(c)) return c;
    } else {
      return c; // 交给 PATH 解析
    }
  }
  return "python3";
}

const args = process.argv.slice(2);
if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
  console.log(`hotel-profile — 酒店价格与全档案批量采集

用法:
  hotel-profile --mode list    --limit 1       列表页价格快照
  hotel-profile --mode profile --limit 10      详情页全档案（房型/设施/周边/政策）
  hotel-profile --mode discover --from-list <URL>   从列表页发现酒店 ID
  hotel-profile --probe                        自检 bsk 连通与协作协议
  hotel-profile --calibrate <URL>              导出页面结构用于校准选择器

前置:
  1. 已安装 bsk CLI（https://github.com/Tencent/BrowserSkill）并在 PATH
  2. 浏览器扩展已连接，且浏览器里已登录目标平台
  3. 首次使用: cp config/hotels.example.csv config/hotels.csv

配置: config/settings.json（可用 config/settings.local.json 本机覆盖）
输出: ./output 下的 CSV / JSONL / XLSX

Python 解释器: HOTEL_PROFILE_PYTHON / PYTHON 环境变量，否则自动尝试 python3 → python → py
`);
  process.exit(0);
}

const py = pickPython();
const child = spawn(py, [script, ...args], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  windowsHide: true,
});

child.on("error", (e) => {
  console.error(`[hotel-profile] 无法启动 Python（${py}）: ${e.message}`);
  console.error("[hotel-profile] 请安装 Python 3.9+，或设置 HOTEL_PROFILE_PYTHON 指向解释器路径。");
  process.exit(1);
});
child.on("exit", (code) => process.exit(code ?? 1));
