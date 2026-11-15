# -*- coding: utf-8 -*-
import os, shutil, json, zipfile
src = r"D:/DSH/home/skills/hotel-profile"
dst = r"D:/项目开发/hotel-profile-workbuddy/hotel-profile"

os.makedirs(os.path.join(dst, "scripts", "config"), exist_ok=True)
os.makedirs(os.path.join(dst, "references"), exist_ok=True)

for f in ["ctrip_hotel.py", "ctrip_profile.py", "profile_extract.js", "verify_probe.py"]:
    shutil.copy2(os.path.join(src, "scripts", f), os.path.join(dst, "scripts", f))

for f in ["selectors.json", "hotels.example.csv", "hotels.profile.example.csv"]:
    shutil.copy2(os.path.join(src, "config", f), os.path.join(dst, "scripts", "config", f))

# 技能包内自带真实清单文件名（空表头），首次运行时由 AI 填充
open(os.path.join(dst, "scripts", "config", "hotels.csv"), "w", encoding="utf-8").write(
    "hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note\n")
open(os.path.join(dst, "scripts", "config", "hotels.profile.csv"), "w", encoding="utf-8").write(
    "hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note\n")

files = []
for root, dirs, fs in os.walk(dst):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in fs:
        p = os.path.join(root, f)
        files.append(os.path.relpath(p, os.path.dirname(dst)))
print("PACK_FILES", len(files))
for x in sorted(files): print(" ", x)

zp = os.path.join(r"D:/项目开发/hotel-profile-workbuddy", "hotel-profile.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for rel in files:
        z.write(os.path.join(os.path.dirname(dst), rel), rel)
print("ZIP", zp, os.path.getsize(zp), "bytes")
