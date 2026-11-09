#!/usr/bin/env python3
"""HTML pages for the courseware web app (landing page and workshop).

Kept separate from main.py so the API module stays readable. Pages are
plain string templates with __TOKEN__ placeholders filled by .replace(),
which avoids brace escaping problems with the inline CSS and JS.

Design language follows the lesson courseware itself: paper background,
ink text, vermilion accent, teal secondary, KaiTi display characters,
fixed neat layout that also works on a phone.
"""
import html

CSS = """
:root{
  --paper:#FAF6EF; --card:#FFFFFF; --ink:#263238; --sub:#6B7A80;
  --red:#C8432B; --teal:#1F7A6D; --gold:#E3A72F; --line:#E7DFD2;
}
*{box-sizing:border-box; -webkit-tap-highlight-color:transparent;}
body{margin:0; background:var(--paper); color:var(--ink);
  font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;}
header{background:var(--ink); color:#fff; padding:13px 20px;
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;}
header .brand{font-size:19px; font-weight:700; letter-spacing:1px;}
header .brand small{font-weight:400; color:#B9C6CA; font-size:12.5px; margin-left:8px;}
header .spacer{flex:1;}
header .userbox{display:flex; align-items:center; gap:9px; font-size:13.5px;}
header .userbox img{width:30px; height:30px; border-radius:50%; border:2px solid #57686E;}
header .avatar-fallback{width:30px; height:30px; border-radius:50%; background:var(--red);
  color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700;}
header a.logout{color:#E8D9B0; text-decoration:none; border:1px solid #57686E;
  padding:4px 12px; border-radius:999px; font-size:13px;}
main{max-width:880px; margin:0 auto; padding:22px 16px 34px;}
.card{background:var(--card); border:1px solid var(--line); border-radius:16px; padding:20px;}
.hero{text-align:center; padding:38px 20px 30px;}
.hero h1{font-family:"Kaiti SC","STKaiti","KaiTi",serif; font-size:42px; margin:0 0 6px; letter-spacing:2px;}
.hero .en{color:var(--sub); font-size:14px; letter-spacing:1px; margin-bottom:16px;}
.hero p.lead{font-size:17px; line-height:1.75; color:#3D4A4F; max-width:560px; margin:0 auto 22px;}
.features{display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-bottom:26px;}
.features span{background:var(--paper); border:1px solid var(--line); border-radius:999px;
  padding:5px 14px; font-size:13.5px; color:#3D4A4F;}
.btn{display:inline-block; border:none; border-radius:999px; padding:12px 26px;
  font-size:16px; font-weight:600; cursor:pointer; font-family:inherit; text-decoration:none;}
.btn.primary{background:var(--red); color:#fff;}
.btn.primary:hover{background:#A8361F;}
.btn.teal{background:var(--teal); color:#fff;}
.btn.teal:hover{background:#166355;}
.btn.ghost{background:#fff; color:var(--ink); border:1.5px solid var(--line);}
.btn[disabled]{opacity:.45; cursor:not-allowed;}
.btn.small{padding:7px 16px; font-size:14px;}
.note{font-size:13px; color:var(--sub); margin-top:12px;}
.banner{background:#FDF0EC; border:1px solid #EFC4B8; color:#8C2B18;
  border-radius:12px; padding:11px 15px; font-size:14.5px; margin-bottom:16px; text-align:center;}
footer{max-width:880px; margin:0 auto; padding:0 16px 28px; font-size:12px;
  color:var(--sub); line-height:1.8; text-align:center;}
.quota{font-size:14px; color:var(--sub);}
.quota b{color:var(--red); font-size:17px;}
h2.sec{font-size:17px; margin:22px 0 10px;}
h2.sec:first-child{margin-top:0;}
input[type=text]{font-family:inherit; font-size:15px; color:var(--ink);
  border:1.5px solid var(--line); border-radius:10px; padding:9px 11px; width:100%;
  background:#FFFDF8;}
input[type=text]:focus{outline:none; border-color:var(--gold);}
.title-input{max-width:420px;}
table.rows{width:100%; border-collapse:separate; border-spacing:0 8px;}
table.rows th{font-size:13px; color:var(--sub); text-align:left; font-weight:500; padding:0 4px;}
table.rows td{padding:0 4px;}
td.c-ch{width:74px;} td.c-ch input{text-align:center; font-size:19px;
  font-family:"Kaiti SC","STKaiti","KaiTi",serif;}
td.c-act{width:44px; text-align:center;}
button.del{border:1.5px solid var(--line); background:#fff; color:var(--sub);
  width:32px; height:32px; border-radius:50%; cursor:pointer; font-size:15px;}
button.del:hover{border-color:var(--red); color:var(--red);}
textarea{width:100%; min-height:96px; font-family:inherit; font-size:14.5px; color:var(--ink);
  border:1.5px solid var(--line); border-radius:10px; padding:10px 12px; background:#FFFDF8;
  line-height:1.7;}
textarea:focus{outline:none; border-color:var(--gold);}
.row-actions{display:flex; gap:9px; flex-wrap:wrap; margin-top:6px;}
.status{margin-top:18px; font-size:15.5px; min-height:26px; text-align:center;}
.status .err{color:var(--red); font-weight:600;}
.downloads{display:none; gap:10px; justify-content:center; flex-wrap:wrap; margin-top:12px;}
.hintline{font-size:12.5px; color:var(--sub); text-align:center; margin-top:8px;}
"""

_FOOTER = """
<footer>
  笔顺数据来自 Make Me a Hanzi，适用 Arphic Public License（许可全文在 GitHub 仓库
  skills/hanzi-stroke-courseware/references/ARPHICPL.TXT）。<br>
  汉字动画库 Hanzi Writer，MIT 许可。开发者接口见仓库 services/courseware-api/README.md。
</footer>
"""

LANDING = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文韬中文 · 课件工坊</title>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="brand">文韬中文<small>Wentao Chinese</small></div>
</header>
<main>
  __ERROR__
  <section class="card hero">
    <h1>课件工坊</h1>
    <div class="en">WENTAO CHINESE COURSEWARE STUDIO</div>
    <p class="lead">输入一课的生字表，自动生成带笔顺动画的课件：
    一份能在浏览器里描红互动的 HTML，和一份放映时笔顺自己动的 PPT。</p>
    <div class="features">
      <span>✍ 笔顺动画</span><span>🖍 描红挑战</span><span>🃏 配对游戏</span><span>📊 PPT + HTML 双格式</span>
    </div>
    __LOGIN__
    <div class="note">免费版：每个账号每天可生成 __LIMIT__ 次。</div>
  </section>
</main>
__FOOTER__
</body>
</html>
"""

WORKSHOP = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>课件工坊 · 文韬中文</title>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="brand">文韬中文<small>课件工坊</small></div>
  <div class="spacer"></div>
  <div class="userbox">
    __AVATAR__
    <span>__EMAIL__</span>
    <a class="logout" href="/auth/logout">退出</a>
  </div>
</header>
<main>
  <section class="card">
    <div style="display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;">
      <h2 class="sec" style="margin:0;">这一课的生字</h2>
      <span class="quota">今日还可生成 <b id="quotaLeft">__REMAINING__</b> 次（免费版每天 __LIMIT__ 次）</span>
    </div>

    <h2 class="sec">标题（可不填）</h2>
    <input type="text" id="lessonTitle" class="title-input" placeholder="例如：第三课 生字" maxlength="60">

    <h2 class="sec">生字表</h2>
    <table class="rows">
      <thead><tr><th>字</th><th>拼音</th><th>释义</th><th></th></tr></thead>
      <tbody id="rowsBody"></tbody>
    </table>
    <div class="row-actions">
      <button class="btn ghost small" id="btnAdd" type="button">＋ 添加一行</button>
    </div>

    <h2 class="sec">批量粘贴</h2>
    <textarea id="bulkText" placeholder="每行一个字，格式：字 拼音 释义，用空格或逗号分开。例如：
永 yǒng 永远 · forever
人 rén 人 · person"></textarea>
    <div class="row-actions">
      <button class="btn ghost small" id="btnParse" type="button">解析到上面的表格</button>
      <span class="note" id="parseMsg" style="margin-top:6px;"></span>
    </div>

    <div style="text-align:center; margin-top:24px;">
      <button class="btn primary" id="btnGen" type="button">生成课件</button>
    </div>
    <div class="status" id="status"></div>
    <div class="downloads" id="downloads">
      <a class="btn teal" id="dlPptx" href="#">⬇ 下载 PPT</a>
      <a class="btn teal" id="dlHtml" href="#">⬇ 下载 HTML</a>
      <a class="btn ghost" id="openHtml" href="#" target="_blank" rel="noopener">在新标签打开 HTML</a>
    </div>
    <div class="hintline">生成需要排队和渲染，免费版大约 1 到 2 分钟，请不要关掉这个页面。</div>
  </section>
</main>
__FOOTER__
<script>
var SAMPLE = [
  {ch:'永', py:'yǒng', mean:'永远 · forever'},
  {ch:'人', py:'rén', mean:'人 · person'},
  {ch:'大', py:'dà', mean:'大 · big'}
];
var rowsBody = document.getElementById('rowsBody');
var statusEl = document.getElementById('status');
var downloadsEl = document.getElementById('downloads');

function addRow(w){
  var tr = document.createElement('tr');
  tr.innerHTML = '<td class="c-ch"><input type="text" maxlength="1" aria-label="字"></td>' +
    '<td><input type="text" aria-label="拼音"></td>' +
    '<td><input type="text" aria-label="释义"></td>' +
    '<td class="c-act"><button type="button" class="del" title="删掉这一行">✕</button></td>';
  var inputs = tr.querySelectorAll('input');
  if (w){ inputs[0].value = w.ch || ''; inputs[1].value = w.py || ''; inputs[2].value = w.mean || ''; }
  tr.querySelector('.del').addEventListener('click', function(){ tr.remove(); });
  rowsBody.appendChild(tr);
}
SAMPLE.forEach(addRow);
document.getElementById('btnAdd').addEventListener('click', function(){ addRow(null); });

document.getElementById('btnParse').addEventListener('click', function(){
  var text = document.getElementById('bulkText').value;
  var lines = text.split(/\\n/), added = 0, skipped = 0;
  lines.forEach(function(line){
    line = line.trim();
    if (!line) return;
    var parts = line.split(/[\\s,，、;；]+/).filter(Boolean);
    if (parts.length < 3){ skipped++; return; }
    addRow({ch: parts[0], py: parts[1], mean: parts.slice(2).join(' ')});
    added++;
  });
  document.getElementById('parseMsg').textContent =
    added ? ('已添加 ' + added + ' 行' + (skipped ? '，跳过 ' + skipped + ' 行（格式不对）' : '') + '。') :
            '没有解析出内容，检查一下格式：每行 字 拼音 释义。';
});

function collect(){
  var words = [], bad = 0;
  rowsBody.querySelectorAll('tr').forEach(function(tr){
    var v = Array.prototype.map.call(tr.querySelectorAll('input'), function(i){ return i.value.trim(); });
    if (!v[0] && !v[1] && !v[2]) return;
    if (!v[0] || v[0].length !== 1 || !v[1] || !v[2]){ bad++; return; }
    words.push({ch: v[0], py: v[1], mean: v[2]});
  });
  return {words: words, bad: bad};
}
function setStatus(html){ statusEl.innerHTML = html; }
function setErr(msg){ setStatus('<span class="err">' + msg + '</span>'); }

var generating = false;
document.getElementById('btnGen').addEventListener('click', function(){
  if (generating) return;
  var got = collect();
  if (got.bad){ setErr('生字表里有 ' + got.bad + ' 行没填完整：每一行都要有字、拼音和释义，字只能填一个。'); return; }
  if (!got.words.length){ setErr('生字表是空的，先填几个字再生成。'); return; }
  if (got.words.length > 20){ setErr('一次最多 20 个字，这次有 ' + got.words.length + ' 个，分成两课吧。'); return; }
  var body = {words: got.words};
  var title = document.getElementById('lessonTitle').value.trim();
  if (title) body.title = title;
  generating = true;
  downloadsEl.style.display = 'none';
  setStatus('正在提交…');
  fetch('/generate', {method: 'POST', headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify(body)})
    .then(function(r){
      return r.json().then(function(j){ return {ok: r.ok, status: r.status, body: j}; });
    })
    .then(function(res){
      if (res.status === 401){ generating = false; setErr('登录已经过期，请退出后重新登录。'); return; }
      if (res.status === 429){ generating = false; setErr(res.body.detail || '今天的免费次数已经用完了，明天再来吧。'); return; }
      if (!res.ok){ generating = false; setErr('提交失败：' + (res.body.detail || ('服务器返回 ' + res.status))); return; }
      if (typeof res.body.quota_remaining === 'number'){
        document.getElementById('quotaLeft').textContent = res.body.quota_remaining;
      }
      poll(res.body.job_id, Date.now());
    })
    .catch(function(){ generating = false; setErr('网络不太顺，提交没成功，请再点一次生成。'); });
});

function poll(jobId, t0){
  fetch('/jobs/' + jobId).then(function(r){ return r.json(); }).then(function(j){
    var sec = Math.round((Date.now() - t0) / 1000);
    if (j.status === 'running'){
      setStatus('生成中…已等 ' + sec + ' 秒（免费版约 1 到 2 分钟）');
      setTimeout(function(){ poll(jobId, t0); }, 4000);
    } else if (j.status === 'done'){
      generating = false;
      setStatus('🎉 生成好了，一共用了 ' + sec + ' 秒。');
      document.getElementById('dlPptx').href = j.files.pptx;
      document.getElementById('dlHtml').href = j.files.html;
      document.getElementById('openHtml').href = j.files.html;
      downloadsEl.style.display = 'flex';
    } else {
      generating = false;
      setErr('这一课生成失败了' + (j.error ? '：' + j.error : '') + '。检查一下生字表，或者稍后再试。');
    }
  }).catch(function(){
    setTimeout(function(){ poll(jobId, t0); }, 5000);
  });
}
</script>
</body>
</html>
"""


def landing_page(google_ready, limit, login_error=None, dev_login=False):
    """Render the logged out landing page."""
    if login_error:
        error = f'<div class="banner">{html.escape(login_error)}</div>'
    else:
        error = ''
    if google_ready:
        login = '<a class="btn primary" href="/auth/google/login">用 Google 登录</a>'
    else:
        login = ('<button class="btn primary" disabled>用 Google 登录</button>'
                 '<div class="note">登录还没有配置好，请联系管理员。</div>')
    if dev_login:
        login += ('<div style="margin-top:14px;"><a href="/auth/dev" '
                  'style="color:var(--sub); font-size:13px;">本地开发登录（DEV_LOGIN）</a></div>')
    return (LANDING.replace('__CSS__', CSS)
            .replace('__ERROR__', error)
            .replace('__LOGIN__', login)
            .replace('__LIMIT__', str(limit))
            .replace('__FOOTER__', _FOOTER))


def workshop_page(user, remaining, limit):
    """Render the logged in workshop page for one user dict."""
    email = html.escape(user.get('email', ''))
    picture = user.get('picture') or ''
    if picture:
        avatar = f'<img src="{html.escape(picture, quote=True)}" alt="">'
    else:
        initial = html.escape((user.get('name') or email or '?')[:1].upper())
        avatar = f'<span class="avatar-fallback">{initial}</span>'
    return (WORKSHOP.replace('__CSS__', CSS)
            .replace('__AVATAR__', avatar)
            .replace('__EMAIL__', email)
            .replace('__REMAINING__', str(remaining))
            .replace('__LIMIT__', str(limit))
            .replace('__FOOTER__', _FOOTER))
