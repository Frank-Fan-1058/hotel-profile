# 更新日志

## v1.0.0（2026-11-15）

首个可发布版本。产品/仓库名：hotel-profile。

- `list` 模式：城市列表页批量价格快照（成交价 / 划线原价 / 评分 / 点评数 / 位置 / 取消政策）。
- `profile` 模式：单家详情页全档案（房型 / 床型 / 面积 / 楼层 / 9 项设施标记 / 周边 POI / 地铁 / 政策 / 简介）。
- `discover` 模式：从列表页自动发现 hotelId。
- 抗反爬：复用真实已登录浏览器、只读渲染 DOM、拟人节奏、遇验证码转人工。
- 依赖解耦：bsk CLI 走 PATH / `BSK_CLI`，本机配置覆盖，缺清单回退模板；不依赖 DSH。
- 离线解析测试 9 项；MIT 许可。
- 已发布：GitHub Release `v1.0.0` 与 npm `hotel-profile@1.0.0`（`npx hotel-profile` 可直接运行）。
