(function(){
  var F = __FIELDS__;
  var clean = function(s){ return (s||'').trim().replace(/[ \t]+/g,' '); };
  var txt = function(e){ return e ? clean(e.innerText || e.textContent || '') : ''; };
  var raw = function(e){ return e ? (e.innerText || e.textContent || '').trim() : ''; };
  var qsa = function(sel){ try { return Array.from(document.querySelectorAll(sel)); } catch(e){ return []; } };

  var one = {};
  Object.keys(F.one || {}).forEach(function(k){
    var v = '';
    (F.one[k] || []).some(function(sel){
      var t = qsa(sel).map(txt).filter(Boolean)[0];
      if (t) { v = t.slice(0, 400); return true; }
      return false;
    });
    one[k] = v || null;
  });

  var longest = {};
  Object.keys(F.longest || {}).forEach(function(k){
    var best = '';
    (F.longest[k] || []).forEach(function(sel){
      qsa(sel).forEach(function(e){ var t = txt(e); if (t.length > best.length) best = t; });
    });
    longest[k] = best ? best.slice(0, 8000) : null;
  });

  var all = {};
  Object.keys(F.all || {}).forEach(function(k){
    var seen = {}, out = [];
    qsa(F.all[k] || '').forEach(function(e){
      var t = (k === 'rooms') ? raw(e) : txt(e);
      if (t && !seen[t]) { seen[t] = 1; out.push(t.slice(0, 900)); }
    });
    all[k] = out;
  });

  var bt = document.body.innerText || '';
  var nb = null;
  var m = bt.match(/附近[\s\S]{0,1800}?(?:在地图上查看|酒店设施|服务及设施|酒店政策)/);
  if (m) nb = m[0].trim().slice(0, 1600);
  var intro = null;
  var m2 = bt.match(/酒店简介[\s\S]{0,1200}?(?:订房必读|服务及设施|酒店政策|点评|附近的酒店)/);
  if (m2) intro = clean(m2[0]).slice(0, 1000);
  var wall = ['登录以查看','立即登录','请登录','安全验证','请拖动','人机验证','访问验证']
    .filter(function(k){ return bt.indexOf(k) >= 0; });

  return { one: one, longest: longest, all: all, nearby_block: nb, intro_block: intro,
           body: bt.slice(0, 14000), url: location.href, title: document.title, login_wall: wall };
})()