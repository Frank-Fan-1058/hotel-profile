# 目标站点页面地图（2026-11-15 实测，仅供校准参考）

> 目标站点会改版。以下类名来自真实 `--calibrate` 与真实详情页 DOM 探针，不是稳定契约。
> 校准文件：`output/calibration.json`（`class_hints` / `price_like` / `body`）。

## URL

| 用途 | 模板 | 状态 |
| --- | --- | --- |
| 首页 | `{base_url}/` | 实测可开 |
| 城市列表页 | `{base_url}/hotels/list?city=2&checkin=2026/11/20&checkout=2026/11/21` | **实测**：9346 家，无风控 |
| 详情页 | `{base_url}/hotels/detail/?hotelId=10000001&checkin=2026/11/20&checkout=2026/11/21` | **实测**：全档案 DOM |

- 日期分隔符是 `/`（settings 里 `date_sep: "/"`）；`-` 要转换。
- 实测 `city=2` → **上海**（不是北京）。其他 city_id 请自行校准。
- 首页默认搜索框：目的地 `input[placeholder="目的地"]`；首页有 risk iframe（`risk_Iframe_t_`），ref 抖动 → **用 CSS 选择器，不用 `@eN`**。
- **hotelId 来源**：列表页 `.hotel-card` 的 `id` 属性（实测 10000001=示例、10000002=星澜、10000003=沐白）；或 `--mode discover` 从页面 HTML 的 `hotelId=` 提取。

## 列表页 CSS 类

| 字段 | 类 | 样例 |
| --- | --- | --- |
| 卡片容器 | `.hotel-card` / `.hotel-list` | 整卡 |
| 酒店名 | `[class*=hotelName]` / `.hotel-title` | 沐白酒店(示例市新港地铁站店) |
| 评分 | `.comment-score` | 4.9 |
| 点评数 | `.comment-num` | 622条点评 |
| 位置 | `.hotel-position` | 近新港地铁站… |
| 促销/取消标签 | `.hotel-tag` | 免费取消 |
| 价格 | `.room-price` / `.price-line` | 未登录时为空 |
| 价格筛选栏 | `.price-quick-choose` | ¥0 - ¥200 …（**不是酒店价格**） |

## 登录态价格 DOM

价格块 `.room-price` 的叶子子元素：

| 类名 | 含义 | 样例 |
| --- | --- | --- |
| `.promotion-tag` | 会员价标签 | 黄金贵宾价 |
| `.discount-tag` | 优惠金额（**不是价格**） | 优惠174 |
| `.delete.delete-tilt` | 划线原价 | ¥1,154 |
| `.sale` | **实付/成交价** | ¥980 / ¥837 / ¥919 |
| `.price-suffix` | 后缀 | 起 |

- **取价铁律**：`sale_price` 取 `.room-price .sale`，`list_price` 取 `.delete`；`price_num` 正则锚定 `¥`（`[¥￥]\s*数字`），杜绝把「优惠174」「连续54位住客好评」误当价格。
- 实测卡：示例 ¥837 起｜星澜 ¥1,154→¥980（优惠174）｜沐白 ¥919 起｜澜庭 ¥775 起。
- 未登录：卡片显示「**登录以查看会员价**」，`room-price` 为空，`price_num=null`、`status=needs_login`。

## 详情页 CSS 类（全档案）

| 字段 | 类 | 样例 |
| --- | --- | --- |
| 酒店名 | `[class*=hotelNameRow_hotelOverview_name]` / `h1` | 示例酒店甲 |
| 地址 | `[class*=hotelAddre]` | 示例市示例区示例路118号显示地图 |
| 电话 | `[class*=hotelContact]` | 电话：000-00000000 |
| 评分/点评 | `[class*=reviewScore]` | 超棒 7,014 条评论（**评分要从正文 4.8 抽，别取这里的 7**） |
| 房型卡片 | `[class*=commonRoomCard__]` / `[class*=mainRoomLi]` | 经典大床房 1张1.8米大床 24平方米 4-12层 Wi-Fi免费 ¥837 |
| 房型名 | `[class*=commonRoomCard-title]` | 经典大床房 |
| 服务及设施 | `[class*=hotelFacilityNew_hotelFacilityNewA]` / `[class*=hotelFacility-container]` | 示例厅/示例吧/停车场/大堂吧/健身室/会议厅… |
| 设施条目 | `[class*=hotelFacility-popular_item]` / `[class*=hotelFacility-normal_drawerItem]` | 充电车位、会议厅收费 |
| 地点/周边 | `[class*=hotelLocationNew]` | 正文「附近 休闲娱乐: 示例体育场（1.2公里）… 在地图上查看」 |
| 地铁 | `[class*=hotelLocation-detail]` | 地铁: 云栖路地铁站 540米 |
| 酒店政策 | `[class*=hotelPolicyNew_hotelPolicyNew]` / `[class*=hotelPolicy-content]` | 入住 14:00后 / 退房 12:00前 |
| 早餐政策 | `[class*=hotelPolicyNew_breakfa]` | 12岁及以下免费 / 成人 ¥158/人 |
| 简介 | 正文「酒店简介」段 | 开业：2025 客房数：173… |
| 亮点标签 | `[class*=hotelOverview_tag]` | 新中式风、拍照出片 |

实测三家设施标记依据：沐白「会议厅收费」、星澜「会议厅/商务中心」、示例「会议厅收费」→ `has_meeting_room=是`；三家设施文本均无「泳池/游泳池」→ `has_pool=否`。标记只反映页面文本，不臆测。

## bsk 协作协议（0.4.0）

`bsk` CLI 对 DOM 动作强制 `cooperate sync` → 拿 `context_id`（不是 `context`）→ **一个动作** → 再 sync。目标站点 risk iframe 频繁报「content/frame changed」，脚本用 `--settle` + 最多 8 次重试吸收。全档案模式**每家用独立 session**（导航/滚动多，复用同一 session 连续 navigate 会触发协作拒绝）。详见 troubleshooting。
