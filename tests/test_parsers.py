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
    "附近\n休闲娱乐: 上海体育场\n（1.2公里）\n休闲娱乐: 上海体育馆\n（890米）\n"
    "地标: 上海交通大学(徐汇校区)\n（1.4公里）\n购物: 港汇恒隆广场\n（990米）\n"
    "地标: 徐家汇体育公园\n（770米）\n购物: 美罗城\n（1.2公里）\n在地图上查看"
)
FACILITIES = (
    "服务及设施\n设施服务\n蒲汇堂\n玥吧\n公共停车场\n充电车位\n大堂吧\n咖啡厅\n足浴\n"
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
        r = P.parse_room(ROOM_TEXT)
        self.assertEqual(r["room_name"], "经典大床房")
        self.assertEqual(r["bed_type"], "1张1.8米大床")
        self.assertEqual(r["area_sqm"], "24")
        self.assertEqual(r["floor"], "4-12层")
        self.assertEqual(r["window"], "有窗")
        self.assertEqual(r["smoke"], "禁烟")
        self.assertEqual(r["price_num"], 837)
        self.assertEqual(r["breakfast"], "无早餐")
        self.assertIn("免费取消", r["cancellation"])


class NearbyTests(unittest.TestCase):
    def test_pois(self):
        pois = P.parse_nearby(NEARBY_TEXT)
        self.assertEqual(len(pois), 6)
        self.assertEqual(pois[0]["category"], "休闲娱乐")
        self.assertEqual(pois[0]["poi_name"], "上海体育场")
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
            "one": {"hotel_name": "上海徐家汇禧玥酒店", "address": "上海徐汇区蒲汇塘路118号",
                    "phone": "电话：\n021-33681237", "score": "超棒\n7,014 条评论"},
            "longest": {"facilities": FACILITIES, "policy": "入住时间：14:00后"},
            "all": {"rooms": [ROOM_TEXT], "facility_items": ["蒲汇堂", "会议厅收费"],
                    "highlights": ["新中式风"]},
            "nearby_block": NEARBY_TEXT, "intro_block": "酒店简介 新中式禅意酒店",
            "body": FACILITIES, "login_wall": [],
        }
        base = {"capture_time": "2026-11-15 15:00:00", "platform_hotel_id": "15018492",
                "hotel_name": "", "city": "上海", "checkin": "2026-11-20",
                "checkout": "2026-11-21",
                "source_url": "{base_url}/hotels/detail/?hotelId=15018492"}
        row, rooms, pois = P.flatten(v, base)
        self.assertEqual(row["hotel_name"], "上海徐家汇禧玥酒店")
        self.assertEqual(row["room_type_count"], 1)
        self.assertEqual(row["nearby_poi_count"], 6)
        self.assertEqual(row["has_meeting_room"], "是")
        self.assertEqual(row["has_pool"], "否")
        self.assertEqual(row["review_count"], "7,014")


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

    def test_normalize_strips_generic_and_notes(self):
        import match_hotels as M
        self.assertEqual(M.normalize("如家酒店(上海南京东路店)"), M.normalize("如家"))

    def test_same_hotel_different_wording(self):
        import match_hotels as M
        self.assertGreater(M.similarity("如家酒店上海南京东路店", "如家酒店(南京东路步行街店)"), 0.6)

    def test_abbreviation_matches_full_name(self):
        import match_hotels as M
        # 简称 vs 全称：包含关系应给高分
        self.assertGreaterEqual(M.similarity("汉庭上海金桥店", "汉庭酒店(上海金桥地铁站店)"), 0.85)

    def test_different_hotels_score_low(self):
        import match_hotels as M
        self.assertLess(M.similarity("全季上海人民广场店", "亚朵上海虹桥店"), 0.5)

    def test_pick_best_accepts_clear_winner(self):
        import match_hotels as M
        cands = [{"id": "1", "name": "汉庭酒店(上海金桥地铁站店)"},
                 {"id": "2", "name": "全季酒店(上海虹桥店)"}]
        best, ranked = M.pick_best("汉庭上海金桥店", cands, threshold=0.72)
        self.assertIsNotNone(best)
        self.assertEqual(best["id"], "1")

    def test_pick_best_rejects_ambiguity(self):
        import match_hotels as M
        # 两个候选几乎同分 → 必须交人工，不能硬猜
        cands = [{"id": "1", "name": "锦江之星上海火车站店"},
                 {"id": "2", "name": "锦江之星上海火车站北广场店"}]
        best, ranked = M.pick_best("锦江之星上海火车站", cands, threshold=0.72)
        if best is not None:
            self.assertGreater(best["score"], 0.92)

    def test_branch_word_breaks_same_brand_tie(self):
        import match_hotels as M
        cands = [{"id": "1", "name": "云和夜泊酒店(上海武宁路环球港店)"},
                 {"id": "2", "name": "云和夜泊酒店(上海浦东国际机场店)"}]
        best, ranked = M.pick_best("云和夜泊 武宁路店", cands, threshold=0.72)
        self.assertIsNotNone(best, "同品牌不同分店应能被地点词区分")
        self.assertEqual(best["id"], "1")

    def test_token_bonus_only_on_hit(self):
        import match_hotels as M
        self.assertGreater(M.token_bonus("汉庭 金桥店", "汉庭酒店(上海金桥地铁站店)"), 0)
        self.assertEqual(M.token_bonus("汉庭 金桥店", "全季酒店(上海虹桥店)"), 0)

    def test_pick_best_returns_none_on_garbage(self):
        import match_hotels as M
        best, ranked = M.pick_best("完全不存在的酒店名称XYZ", [{"id": "1", "name": "汉庭酒店"}])
        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main(verbosity=2)
