# -*- coding: utf-8 -*-
import os, shutil, zipfile, json
src = r'D:/DSH/home/skills/hotel-profile'
base = r'D:/项目开发/hotel-profile-workbuddy'
dst = os.path.join(base, 'pkg')
shutil.rmtree(dst, ignore_errors=True)
os.makedirs(os.path.join(dst, 'scripts'), exist_ok=True)
os.makedirs(os.path.join(dst, 'references'), exist_ok=True)
for f in ['hotel_scraper.py', 'hotel_profile.py', 'match_hotels.py', 'profile_extract.js', 'verify_probe.py']:
    shutil.copy2(os.path.join(src, 'scripts', f), os.path.join(dst, 'scripts', f))
with open(os.path.join(src, 'config', 'settings.json'), encoding='utf-8') as f:
    cfg = json.load(f)
cfg['base_url'] = ''
cfg['output_dir'] = './output'
with open(os.path.join(dst, 'scripts', 'settings.json'), 'w', encoding='utf-8') as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
shutil.copy2(os.path.join(src, 'config', 'selectors.json'), os.path.join(dst, 'scripts', 'selectors.json'))
hdr = 'hotel_id,url,city_id,city,hotel_name,checkin,checkout,room_type,note\n'
for name in ['hotels.csv', 'hotels.profile.csv']:
    with open(os.path.join(dst, 'scripts', name), 'w', encoding='utf-8') as f:
        f.write(hdr)
for name in ['hotels.example.csv', 'hotels.profile.example.csv']:
    shutil.copy2(os.path.join(src, 'config', name), os.path.join(dst, 'scripts', name))
shutil.copy2(os.path.join(src, 'workbuddy', 'SKILL.md'), os.path.join(dst, 'SKILL.md'))
for f in ['data-schema.md', 'anti-detection.md', 'platform-page-map.md', 'install-browser-extension.md']:
    p = os.path.join(src, 'references', f)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(dst, 'references', f))
# 关键：zip 内不带外层壳目录，根 = 技能根，最多 根/二级/文件
files = []
for root, dirs, fs in os.walk(dst):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in fs:
        files.append(os.path.relpath(os.path.join(root, f), dst).replace(os.sep, '/'))
zp = os.path.join(base, 'hotel-profile.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for rel in sorted(files):
        z.write(os.path.join(dst, rel.replace('/', os.sep)), rel)
maxd = max(r.count('/') for r in files)
print('PACK_FILES', len(files), 'MAX_SLASH_DEPTH', maxd)
for x in sorted(files): print(' ', x)
print('ZIP_BYTES', os.path.getsize(zp))