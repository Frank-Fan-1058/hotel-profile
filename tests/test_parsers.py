# -*- coding: utf-8 -*-
"""离线解析测试：不需要浏览器 / bsk / 网络。

运行：python -m unittest discover -s tests -v
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ctrip_hotel as C
import ctrip_profile as P

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
        base = {"capture_time": "2026-11-15 15:00:00", "ctrip_hotel_id": "15018492",
                "hotel_name": "", "city": "上海", "checkin": "2026-11-20",
                "checkout": "2026-11-21",
                "source_url": "https://hotels.ctrip.com/hotels/detail/?hotelId=15018492"}
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
