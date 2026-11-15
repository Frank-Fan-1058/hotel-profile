# -*- coding: utf-8 -*-
"""连通性 / 协作协议自检：python scripts/verify_probe.py [--base-url URL] [--settings FILE]"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 透传用户参数（--base-url / --settings），否则空 base_url 时自检必然失败
sys.exit(subprocess.call(
    [sys.executable, os.path.join(HERE, "scripts", "hotel_scraper.py"), "--probe"] + sys.argv[1:]
))
