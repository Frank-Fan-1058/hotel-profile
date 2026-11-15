# -*- coding: utf-8 -*-
import os, shutil, zipfile, json
src = r'D:/DSH/home/skills/hotel-profile'
base = r'D:/项目开发/hotel-profile-workbuddy'
dst = os.path.join(base, 'hotel-profile')
shutil.rmtree(dst, ignore_errors=True)
os.makedirs(os.path.join(dst, 'scripts', 'config'), exist_ok=True)
os.makedirs(os.path.join(dst, 'references'), exist_ok=True)
for f in ['hotel_scraper.py', 'hotel_profile.py', 'match_hotels.py', 'profile_extract.js', 'verify_probe.py']:
    shutil.copy2(os.path.join(src, 'scripts', f), os.path.join(dst, 'scripts', f))
for f in ['selectors.json', 'hotels.example.csv', 'hotels.profile.example.csv']:
    shutil.copy2(os.path.join(src, 'config', f), os.path.join(dst, 'scripts', 'config', f))
shutil.copy2(os.path.join(src, 'workbuddy', 'SKILL.md'), os.path.join(dst, 'SKILL.md'))
with open(os.path.join(src, 'config', 'settings.json'), encoding='utf-8') as f:
    cfg = json.load(f)
cfg['base_url'] = ''
cfg['output_dir'] = './output'
with open(os.path.join(dst, 'scripts', 'config', 'settings.json'), 'w', encoding='utf-8') as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
hdr = 'hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note\n'
for name in ['hotels.csv', 'hotels.profile.csv']:
    with open(os.path.join(dst, 'scripts', 'config', name), 'w', encoding='utf-8') as f:
        f.write(hdr)
for f in ['data-schema.md', 'anti-detection.md', 'platform-page-map.md', 'install-browser-extension.md']:
    p = os.path.join(src, 'references', f)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(dst, 'references', f))
files = []
for root, dirs, fs in os.walk(dst):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in fs:
        files.append(os.path.relpath(os.path.join(root, f), base))
zp = os.path.join(base, 'hotel-profile.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel in files:
        z.write(os.path.join(base, rel), rel)
print('PACK_FILES', len(files))
for x in sorted(files): print(' ', x)
print('ZIP', os.path.getsize(zp), 'bytes')