# -*- coding: utf-8 -*-
"""连通性 / 协作协议自检：python scripts/verify_probe.py"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.call([sys.executable, os.path.join(HERE, "scripts", "hotel_scraper.py"), "--probe"]))
