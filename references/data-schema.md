# 输出字段口径

## 一、价格快照（list）：prices.csv / .jsonl / .xlsx

一行 = 一次快照（一个酒店卡片）。

| 列 | 含义 | 口径 |
| --- | --- | --- |
| `capture_time` | 抓取时刻 | 本机 `YYYY-MM-DD HH:MM:SS`（Asia/Shanghai） |
| `mode` | `list` | 来源页面类型 |
| `city` / `platform_hotel_id` | 城市、目标站点酒店 ID | 取自输入清单；list 模式 ID 常空 |
| `hotel_name` | 酒店名 | 页面渲染文本 |
| `rating` / `rating_num` | 评分 | 原文 / 抽出的浮点（如 4.9） |
| `review_count` / `review_num` | 点评数 | 原文（如「622条点评」）/ 抽出的整数 |
| `address` | 位置描述 | 如「近外滩 · 南京路步行街」 |
| `checkin` / `checkout` | 入住/离店 | 来自输入或 settings |
| `price` / `sale_price` / `list_price` | 价格 / 目标站点价 / 划线原价 | 原文文本 |
| `price_num` | 可计算价格 | 从 `sale_price`（`.room-price .sale`）抽**锚定 ¥ 的**整数；未登录/无价时为 null。正则只认 `¥`/`￥` 开头的数字，杜绝把「优惠174」「连续54位住客好评」误当价格 |
| `currency` | 币种 | 固定 `CNY` |
| `promo_tags` / `cancellation` | 促销标签 / 取消政策 | 文本 |
| `source_url` | 来源 URL | 实际打开的页面 |
| `status` / `notes` | 见下 | 该行质量 / 失败原因 |

## 二、全档案（profile）：三张表

### hotel_profiles.csv —— 一家一行

| 列 | 含义 | 口径 |
| --- | --- | --- |
| `platform_hotel_id` / `hotel_name` / `city` / `address` / `phone` | 基本信息 | 详情页 `h1` / `hotelAddre` / `hotelContact`；地址含「显示地图」属原文 |
| `rating` / `review_count` | 评分 / 点评数 | 从正文「4.8 超棒」「7,014 条评论」抽出；**评分不取 `reviewScore` 文本里的 7**（那是点评数首位） |
| `room_type_count` | 房型数 | `hotel_rooms.csv` 里该酒店去重后的行数 |
| `facilities` | 服务及设施全文 | 详情页 `服务及设施` 区块 + 设施条目去重拼接，最长 6000 字 |
| `has_meeting_room` / `has_pool` / `has_gym` / `has_parking` / `has_restaurant` / `has_spa` / `has_airport_shuttle` / `has_wifi` / `has_bar` | 设施布尔标记 | 「是」=设施全文出现对应关键词（会议室/会议厅/宴会厅；泳池/游泳池；健身房；停车场；餐厅；SPA；接送机/班车；wifi；酒吧）；「否」=未出现。**只反映页面文本，没写就是否，不臆测也不替用户下结论** |
| `nearby_summary` / `nearby_poi_count` | 周边配套汇总 / POI 数 | 「类别:名称(距离)」串 / `hotel_nearby.csv` 行数 |
| `metro` | 地铁 | 详情页「地铁: X 站 N米」原文 |
| `intro` / `highlights` | 酒店简介 / 亮点标签 | 正文「酒店简介」段 / 概览标签 |
| `policy` / `breakfast_policy` | 酒店政策 / 早餐政策 | 入离时间等 / 儿童与成人早餐价 |
| `status` / `notes` | 见下 | 质量 / 原因 |

### hotel_rooms.csv —— 一个价格方案一行

同一房型常挂多个价格方案（标准价 / 含早价 / 会员价），**每个方案单独一行**，靠 `room_name`+`price_num` 区分：

`room_name` 房型名｜`bed_type` 床型（如「1张1.8米大床」）｜`area_sqm` 面积㎡｜`floor` 楼层｜`window` 有窗/无窗｜`smoke` 禁烟｜`wifi`｜`price_num` / `price_text` 该方案价格｜`plan` 方案标记（标准价 / 方案2…）｜`breakfast` 早餐｜`cancellation` 取消政策｜`availability` 余量。

- 均从房型卡片文本抽取，抽不到留空——**不猜**。
- 「展示其余 N 个房型」「查看更多」这类按钮文案**不是房型**，会被跳过。
- `hotel_profiles.csv` 的 `room_type_count` 是**去重房型名**的数量，不等于本表行数。

### hotel_nearby.csv —— 一个周边 POI 一行

`category` 类别（地铁站/地标/购物/休闲娱乐/火车站…）｜`poi_name` 名称｜`distance` 距离（如「1.2公里」「310米」）。

### hotel_report.xlsx

上面三张表各一个 sheet，带筛选与冻结表头。

## status 取值（两套输出通用）

| 值 | 含义 |
| --- | --- |
| `ok` | 抓到酒店名 |
| `partial` | 有数据但关键字段缺 |
| `needs_login` | 命中登录墙、本次未等人工 |
| `blocked` | 命中风控/验证码 |
| `failed` | 页面无数据或 evaluate 报错 |
| `error` | 脚本异常 |

## 去重 / 历史

- `progress.json`（价格）/ `progress_profile.json`（全档案）的 key = `url 或 hotel_id + checkin + checkout + mode`；已完成跳过。
- CSV 是**追加**的，不覆盖；多次同日运行形成多条快照，`capture_time` 区分。
- 要清空重跑：把 `output/` 下的输出文件移走备份，不要直接删。

## 不编原则

`price_num` 为 null 就是没抓到；设施标记「否」只是页面没出现该词，不等于酒店一定没有；`tax_included` 页面没写就留空。所有事实来自当次渲染 DOM，Source URL 可回溯。
