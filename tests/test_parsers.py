# -*- coding: utf-8 -*-
"""离线解析测试：不需要浏览器 / bsk / 网络。

运行：python -m unittest discover -s tests -v
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import hotel_scraper as C
import hotel_profile as P
import match_hotels  # noqa: F401  (供 MatchTests 使用)

ROOM_TEXT = (
    "经典大床房\n4\n1张1.8米大床\n有窗\n禁烟\n24平方米 | 4-12层\nWi-Fi免费\n"
    "房间详情\n房型摘要\n可住人数\n今日价格\n无早餐\n入住当天18:00前可免费取消\n"
    "需等待确认(5分钟)\n在线付\n至多3间\n黄金贵宾价\n¥837\n仅剩1间\n预订"
)
NEARBY_TEXT = (
    "附近\n休闲娱乐: 示例体育场\n（1.2公里）\n休闲娱乐: 示例体育馆\n（890米）\n"
    "地标: 示例大学(云栖校区)\n（1.4公里）\n购物: 示例购物中心\n（990米）\n"
    "地标: 云栖体育公园\n（770米）\n购物: 示例商城\n（1.2公里）\n在地图上查看"
)
FACILITIES = (
    "服务及设施\n设施服务\n示例厅\n示例吧\n公共停车场\n充电车位\n大堂吧\n咖啡厅\n足浴\n"
    "行李寄存免费\n商务服务\n共享办公空间\n会议厅收费\n多媒体演示系统\n公用区wifi免费"
)


class PriceTests(unittest.TestCase):
    def test_anchor_yen(self):
        self.assertEqual(C.to_price("¥980"), 980)
        self.assertEqual(C.to_price("¥1,154"), 1154)
        self.assertEqual(C.to_price("¥1,014"), 1014)

    def test_discount_is_not_a_price(self):
        # 回归：旧正则货币符号可选，"优惠174" 被当成价格
        self.assertIsNone(C.to_price("优惠174"))
        self.assertIsNone(C.to_price("连续54位住客好评"))


class RoomTests(unittest.TestCase):
    def test_room_fields(self):
        r = P.parse_room(ROOM_TEXT)[0]
        self.assertEqual(r["room_name"], "经典大床房")
        self.assertEqual(r["bed_type"], "1张1.8米大床")
        self.assertEqual(r["area_sqm"], "24")
        self.assertEqual(r["floor"], "4-12层")
        self.assertEqual(r["window"], "有窗")
        self.assertEqual(r["smoke"], "禁烟")
        self.assertEqual(r["price_num"], 837)
        self.assertEqual(r["breakfast"], "无早餐")
        self.assertIn("免费取消", r["cancellation"])


class RoomPlanTests(unittest.TestCase):
    """同一房型多个价格方案（标准价/含早价）必须各算一行。"""

    MULTI = ("高级大床房\n2\n1张1.8米大床\n有窗\n禁烟\n28平方米 | 4-7层\n"
             "Wi-Fi免费\n无早餐\n¥883\n1份早餐\n¥963\n仅剩2间")

    def test_multiple_plans_split(self):
        rows = P.parse_room(self.MULTI)
        self.assertEqual(len(rows), 2, "两个价格方案应拆成两行")
        self.assertEqual([r["price_num"] for r in rows], [883, 963])
        self.assertEqual(rows[0]["room_name"], rows[1]["room_name"])

    def test_button_row_is_not_a_room(self):
        self.assertEqual(P.parse_room("展示其余1个房型"), [])
        self.assertEqual(P.parse_room("查看更多"), [])


class NearbyTests(unittest.TestCase):
    def test_pois(self):
        pois = P.parse_nearby(NEARBY_TEXT)
        self.assertEqual(len(pois), 6)
        self.assertEqual(pois[0]["category"], "休闲娱乐")
        self.assertEqual(pois[0]["poi_name"], "示例体育场")
        self.assertEqual(pois[0]["distance"], "1.2公里")
        self.assertEqual(pois[1]["distance"], "890米")


class FlagTests(unittest.TestCase):
    def test_flags_from_text(self):
        f = P.derive_flags(FACILITIES)
        self.assertEqual(f["has_meeting_room"], "是")
        self.assertEqual(f["has_pool"], "否")
        self.assertEqual(f["has_wifi"], "是")
        self.assertEqual(f["has_parking"], "是")


class FlattenTests(unittest.TestCase):
    def test_flat_row(self):
        v = {
            "one": {"hotel_name": "示例酒店甲", "address": "示例市示例区示例路118号",
                    "phone": "电话：\n000-00000000", "score": "超棒\n7,014 条评论"},
            "longest": {"facilities": FACILITIES, "policy": "入住时间：14:00后"},
            "all": {"rooms": [ROOM_TEXT], "facility_items": ["示例厅", "会议厅收费"],
                    "highlights": ["新中式风"]},
            "nearby_block": NEARBY_TEXT, "intro_block": "酒店简介 新中式禅意酒店",
            "body": FACILITIES, "login_wall": [],
        }
        base = {"capture_time": "2026-11-15 15:00:00", "platform_hotel_id": "10000001",
                "hotel_name": "", "city": "上海", "checkin": "2026-11-20",
                "checkout": "2026-11-21",
                "source_url": "{base_url}/hotels/detail/?hotelId=10000001"}
        row, rooms, pois = P.flatten(v, base)
        self.assertEqual(row["hotel_name"], "示例酒店甲")
        self.assertEqual(row["room_type_count"], 1)
        self.assertEqual(row["nearby_poi_count"], 6)
        self.assertEqual(row["has_meeting_room"], "是")
        self.assertEqual(row["has_pool"], "否")
        self.assertEqual(row["review_count"], "7014")   # 千分位逗号已清除


class ConfigTests(unittest.TestCase):
    def test_output_absolute(self):
        self.assertEqual(C.output_dir({"output_dir": "/tmp/x"}), "/tmp/x")

    def test_output_relative(self):
        d = C.output_dir({"output_dir": "./output"})
        self.assertTrue(os.path.isabs(d) and d.endswith("output"))

    def test_resolve_input_fallback(self):
        p = C.resolve_input("__no_such_file__.csv", "hotels.example.csv")
        self.assertTrue(p.endswith("hotels.example.csv"))


class MatchTests(unittest.TestCase):
    """模糊匹配：用户导入的名称常与站点正式名不一致。"""

    def test_normalize_keeps_branch_words(self):
        """分店名在括号里，必须保留——删掉会让同品牌所有分店同分（回归 2026-11-16 缺陷）。"""
        import match_hotels as M
        self.assertIn("南京东路", M.normalize("星澜酒店(南京东路店)"))
        self.assertNotEqual(M.normalize("星澜酒店(南京东路店)"),
                            M.normalize("星澜酒店(浦东机场店)"))
        # 通用词仍然被清掉
        self.assertEqual(M.normalize("星澜酒店"), "星澜")

    def test_same_hotel_different_wording(self):
        import match_hotels as M
        self.assertGreater(M.similarity("星澜酒店上海南京东路店", "星澜酒店(南京东路步行街店)"), 0.6)

    def test_abbreviation_matches_full_name(self):
        import match_hotels as M
        # 简称 vs 全称：包含关系应给高分
        self.assertGreaterEqual(M.similarity("沐白示例新港店", "沐白酒店(示例市新港地铁站店)"), 0.85)

    def test_different_hotels_score_low(self):
        import match_hotels as M
        self.assertLess(M.similarity("近江示例人民广场店", "云栖示例虹桥店"), 0.5)

    def test_pick_best_accepts_clear_winner(self):
        import match_hotels as M
        cands = [{"id": "1", "name": "沐白酒店(示例市新港地铁站店)"},
                 {"id": "2", "name": "近江酒店(示例市虹桥店)"}]
        best, ranked = M.pick_best("沐白示例新港店", cands, threshold=0.72)
        self.assertIsNotNone(best)
        self.assertEqual(best["id"], "1")

    def test_pick_best_rejects_ambiguity(self):
        import match_hotels as M
        # 两个候选几乎同分 → 必须交人工，不能硬猜
        cands = [{"id": "1", "name": "澜庭之星示例火车站店"},
                 {"id": "2", "name": "澜庭之星示例火车站北广场店"}]
        best, ranked = M.pick_best("澜庭之星示例火车站", cands, threshold=0.72)
        if best is not None:
            self.assertGreater(best["score"], 0.92)

    def test_branch_word_breaks_same_brand_tie(self):
        import match_hotels as M
        cands = [{"id": "1", "name": "星澜酒店(示例市云栖路中心店)"},
                 {"id": "2", "name": "星澜酒店(示例市新港机场店)"}]
        best, ranked = M.pick_best("星澜 云栖路店", cands, threshold=0.72)
        self.assertIsNotNone(best, "同品牌不同分店应能被地点词区分")
        self.assertEqual(best["id"], "1")

    def test_token_bonus_only_on_hit(self):
        import match_hotels as M
        self.assertGreater(M.token_bonus("沐白 新港店", "沐白酒店(示例市新港地铁站店)"), 0)
        self.assertEqual(M.token_bonus("沐白 新港店", "近江酒店(示例市虹桥店)"), 0)

    def test_pick_best_returns_none_on_garbage(self):
        import match_hotels as M
        best, ranked = M.pick_best("完全不存在的酒店名称XYZ", [{"id": "1", "name": "沐白酒店"}])
        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main(verbosity=2)
