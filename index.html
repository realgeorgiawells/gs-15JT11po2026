<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>Goalscraper</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icons/favicon-32.png">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Goalscraper">
<meta name="theme-color" content="#0f1114">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=UnifrakturMaguntia&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0f1114; --panel:#181b20; --panel2:#1d2026; --line:#262a31; --line2:#30353d;
  --text:#ece8df; --mute:#9aa0a8; --faint:#6c727a;
  --gold:#c9a54a; --gold-hi:#e8cf86; --gold-lo:#7d5f22;
  --red:#e5484d; --amber:#e0a63a; --green:#4cc38a;
  --engraved:"Cinzel",Georgia,serif; --gothic:"UnifrakturMaguntia",Georgia,serif;
  --plain:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
  --bar:66px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{color-scheme:dark}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--text);font:15px/1.4 var(--plain);
  background-image:radial-gradient(ellipse at 50% -15%,rgba(201,165,74,.08),transparent 50%);
  padding-bottom:calc(var(--bar) + env(safe-area-inset-bottom) + 18px)}
.wrap{max-width:720px;margin:0 auto;padding:0 14px}
button{font:inherit;color:inherit}
/* header */
header{position:sticky;top:0;z-index:15;background:rgba(15,17,20,.92);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  border-bottom:1px solid var(--line);padding-top:env(safe-area-inset-top)}
.hd{display:flex;align-items:center;gap:10px;height:56px}
.hd img{width:34px;height:34px}
.hd h1{margin:0;font:400 28px/1 var(--gothic);flex:1;
  background:linear-gradient(180deg,var(--gold-hi),var(--gold) 60%,var(--gold-lo));-webkit-background-clip:text;background-clip:text;color:transparent}
.menu-btn{width:40px;height:40px;border-radius:10px;border:1px solid var(--line2);background:var(--panel);display:grid;place-items:center;cursor:pointer}
.menu-btn svg{width:20px;height:20px;stroke:var(--gold);fill:none;stroke-width:2;stroke-linecap:round}
.mock{font:600 10.5px/1 var(--plain);letter-spacing:.5px;color:#1b1610;background:var(--gold);border-radius:999px;padding:3px 7px;margin-right:4px}
/* section head */
.sh{padding:16px 2px 10px}
.sh h2{margin:0;font:700 15px/1.2 var(--engraved);letter-spacing:3px;color:var(--gold);text-transform:uppercase}
.sh p{margin:4px 0 0;color:var(--mute);font-size:13px}
.sh .meta{margin-top:6px;font-size:12px;color:var(--faint)}
/* list panel */
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.note{margin-top:10px;padding:10px 12px;border-radius:12px;border:1px solid rgba(224,166,58,.35);background:rgba(224,166,58,.07);
  color:#ecd29a;font-size:13px}
.note b{font-family:var(--engraved);letter-spacing:1px;font-size:11.5px}
/* rows */
.row{display:grid;grid-template-columns:54px 1fr auto;gap:10px;align-items:center;padding:10px 12px;border-top:1px solid var(--line);cursor:pointer}
.row:first-child{border-top:0}
.row:active{background:var(--panel2)}
.sc{font:800 19px/1 var(--plain);font-variant-numeric:tabular-nums;text-align:center;letter-spacing:-.3px}
.sc small{display:block;font:700 9px/1 var(--engraved);letter-spacing:1px;color:var(--faint);margin-top:4px}
.mid{min-width:0}
.teams{font:700 15.5px/1.25 var(--plain);overflow-wrap:anywhere}
.teams .pk{color:var(--gold-hi)}
.teams .v{color:var(--faint);font-weight:500;margin:0 3px}
.sub{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:3px;font-size:12px;color:var(--faint)}
.sub .tm{color:var(--text);font-weight:700;font-variant-numeric:tabular-nums;font-size:13px}
.sub .cp{font:700 10px/1.2 var(--engraved);letter-spacing:1px;color:var(--gold);text-transform:uppercase}
.x{color:var(--red);font-weight:900}
.kf{text-align:right}
.kf b{display:block;font:800 17px/1 var(--plain);font-variant-numeric:tabular-nums}
.kf i{display:block;font-style:normal;font-size:10.5px;color:var(--mute);margin-top:3px;white-space:nowrap}
.chip{display:inline-flex;align-items:center;padding:1px 7px;border-radius:999px;font:600 10.5px/1.5 var(--plain);border:1px solid}
.chip.amber{color:#f2c56b;border-color:rgba(224,166,58,.4);background:rgba(224,166,58,.1)}
.chip.grey{color:var(--mute);border-color:var(--line2)}
.chip.gold{color:var(--gold-hi);border-color:rgba(201,165,74,.45);background:rgba(201,165,74,.08)}
/* details (under the hood) */
.det{display:none;padding:2px 12px 14px 76px;border-top:0;background:linear-gradient(180deg,transparent,rgba(255,255,255,.015))}
.det.open{display:block}
.wdl{display:flex;height:8px;border-radius:5px;overflow:hidden;margin:6px 0 4px;background:var(--line)}
.wdl span:nth-child(1){background:var(--green)}.wdl span:nth-child(2){background:#6c727a}.wdl span:nth-child(3){background:#5b8def}
.wdlk{display:flex;justify-content:space-between;font-size:11.5px;color:var(--mute);font-variant-numeric:tabular-nums}
.tr{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;margin-top:9px}
.tr .n{font-weight:600;font-size:13.5px}
.rt{display:flex;gap:9px;font-variant-numeric:tabular-nums}
.rt span{min-width:28px;text-align:center;font:800 14px/1 var(--plain)}
.rt i{display:block;font:700 7.5px/1 var(--engraved);font-style:normal;letter-spacing:1px;color:var(--faint);margin-top:3px}
.dl{margin-top:10px;font-size:12.5px;color:#cfcac0;line-height:1.6}
.dl b{font-variant-numeric:tabular-nums}
.gh{padding:8px 12px;font:700 10px/1.2 var(--engraved);letter-spacing:1.6px;color:var(--faint);text-transform:uppercase;border-top:1px solid var(--line);background:rgba(255,255,255,.015)}
.gh:first-child{border-top:0}
.dim .row .teams,.dim .row .kf b{opacity:.85}
/* selected tab */
.count{margin-top:14px;padding:14px;border-radius:14px;border:1px solid rgba(201,165,74,.35);
  background:linear-gradient(180deg,rgba(201,165,74,.10),rgba(201,165,74,.03));text-align:center}
.count .k{font:700 11px/1 var(--engraved);letter-spacing:3px;color:var(--gold)}
.count .t{font:800 40px/1.1 var(--plain);font-variant-numeric:tabular-nums;letter-spacing:1px;margin-top:6px}
.count .g{font-weight:700;font-size:15px;margin-top:4px}
.count .m{font-size:12px;color:var(--mute);margin-top:2px}
.srow{grid-template-columns:52px 1fr}
.srow .ko{font:800 17px/1 var(--plain);font-variant-numeric:tabular-nums;text-align:center}
.srow .ko small{display:block;font:600 10px/1.2 var(--plain);color:var(--faint);margin-top:4px}
.labels{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
.fold{display:flex;align-items:center;justify-content:space-between;width:100%;margin-top:12px;padding:11px 14px;border-radius:12px;
  border:1px solid var(--line);background:var(--panel);cursor:pointer;font:700 11.5px/1 var(--engraved);letter-spacing:2px;color:var(--mute)}
.fold svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;transition:transform .2s}
.fold.open svg{transform:rotate(180deg)}
/* controls */
.controls{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}
.controls input{grid-column:1/-1}
.controls input,.controls select{width:100%;padding:8px 10px;border-radius:10px;border:1px solid var(--line2);background:#121418;color:var(--text);font:inherit;font-size:14px}
.minis{display:flex;gap:5px;margin-top:6px;flex-wrap:wrap}
.mini{font:700 11px/1 var(--plain);padding:4px 6px;border-radius:6px;background:var(--panel2);border:1px solid var(--line);font-variant-numeric:tabular-nums}
.mini i{font-style:normal;font-family:var(--engraved);font-size:9px;letter-spacing:.8px;color:var(--faint);margin-right:4px}
/* record / coverage / how */
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
.stat .k{font:700 10px/1.2 var(--engraved);letter-spacing:1.6px;color:var(--gold);text-transform:uppercase}
.stat .v{font:800 24px/1.2 var(--plain);font-variant-numeric:tabular-nums;margin-top:4px}
.stat .s{font-size:12px;color:var(--faint)}
.kv{display:flex;justify-content:space-between;gap:12px;padding:10px 14px;border-top:1px solid var(--line);font-size:13.5px}
.kv:first-child{border-top:0}.kv span:first-child{color:var(--mute)}
.log{padding:10px 14px;border-top:1px solid var(--line);font-size:13px;color:#cfcac0}
.log:first-child{border-top:0}.log small{display:block;color:var(--faint);font-size:11.5px}
.prose{padding:4px 14px 14px;font-size:14px;color:#d6d1c6}
.prose h3{font:700 12px/1.3 var(--engraved);letter-spacing:2px;color:var(--gold);margin:16px 0 4px;text-transform:uppercase}
.back{display:inline-flex;align-items:center;gap:6px;margin-top:12px;background:none;border:0;color:var(--mute);cursor:pointer;font:700 11px/1 var(--engraved);letter-spacing:2px;padding:6px 0}
.back svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2}
/* menu sheet */
.scrim{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:30;display:none}
.scrim.on{display:block}
.sheet{position:fixed;top:calc(env(safe-area-inset-top) + 60px);right:14px;z-index:31;width:240px;display:none;
  background:var(--panel2);border:1px solid var(--line2);border-radius:14px;box-shadow:0 18px 40px rgba(0,0,0,.6);overflow:hidden}
.sheet.on{display:block}
.sheet button{display:flex;align-items:center;gap:10px;width:100%;padding:13px 14px;background:none;border:0;border-top:1px solid var(--line);
  cursor:pointer;text-align:left;font-size:14.5px}
.sheet button:first-child{border-top:0}
.sheet svg{width:18px;height:18px;stroke:var(--gold);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
/* bottom bar */
nav{position:fixed;left:0;right:0;bottom:0;z-index:20;padding-bottom:env(safe-area-inset-bottom);
  background:#14161a;border-top:1px solid var(--line2)}
nav .in{max-width:720px;margin:0 auto;display:grid;grid-template-columns:repeat(5,1fr);height:var(--bar)}
nav button{background:none;border:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;cursor:pointer;
  color:var(--faint);font:700 9.5px/1.1 var(--engraved);letter-spacing:.6px;text-transform:uppercase;text-align:center;position:relative;padding:0 2px}
nav button svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
nav button.on{color:var(--gold-hi)}
nav button.on::before{content:"";position:absolute;top:0;left:25%;right:25%;height:2px;background:var(--gold);box-shadow:0 0 8px var(--gold)}
.hidden{display:none!important}
.banner{margin-top:12px;padding:10px 12px;border-radius:12px;font-size:13px;border:1px solid}
.banner b{font-family:var(--engraved);letter-spacing:1px;font-size:11.5px}
.banner.stale{border-color:rgba(229,72,77,.5);background:rgba(229,72,77,.08);color:#f3b9bb}
.banner.new{border-color:rgba(76,195,138,.45);background:rgba(76,195,138,.07);color:#bfead3}
.daystr{font-size:12px;color:var(--faint);padding:8px 2px 0}
.res{font:700 11.5px/1.5 var(--plain);padding:1px 7px;border-radius:999px;border:1px solid;white-space:nowrap}
.res.won{color:#7fdcaf;border-color:rgba(76,195,138,.4);background:rgba(76,195,138,.1)}
.res.lost{color:#f3a0a3;border-color:rgba(229,72,77,.45);background:rgba(229,72,77,.1)}
.res.void,.res.pending{color:var(--mute);border-color:var(--line2)}
.cov{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:10px 14px;border-top:1px solid var(--line)}
.cov:first-child{border-top:0}
.vb{font:800 12.5px/1 var(--plain);min-width:34px;text-align:center;padding:6px 0;border-radius:8px;background:var(--panel2);color:var(--gold-hi)}
.cov .t{font-weight:600;font-size:14px}.cov .m{font-size:11.5px;color:var(--faint)}
.chip.green{color:#7fdcaf;border-color:rgba(76,195,138,.4);background:rgba(76,195,138,.1)}
.chip.red{color:#f3a0a3;border-color:rgba(229,72,77,.45);background:rgba(229,72,77,.1)}
.subtabs{display:flex;gap:6px;margin:10px 0}
.subtabs button{flex:1;padding:8px;border-radius:10px;border:1px solid var(--line2);background:var(--panel);color:var(--mute);
  font:700 10.5px/1 var(--engraved);letter-spacing:1.4px;cursor:pointer}
.subtabs button.on{color:#1b1610;background:var(--gold);border-color:var(--gold)}
.empty{padding:28px 16px;text-align:center;color:var(--mute)}
.empty b{display:block;font:700 13px/1.4 var(--engraved);letter-spacing:2px;color:var(--gold);margin-bottom:6px}
</style>
</head>
<body>
<header><div class="wrap hd">
  <img src="logo.svg" alt="">
  <h1>Goalscraper</h1>
  <button class="menu-btn" id="menuBtn" aria-label="Menu"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
</div></header>

<div class="scrim" id="scrim"></div>
<div class="sheet" id="sheet">
  <button data-go="all"><svg viewBox="0 0 24 24"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></svg>All games</button>
  <button data-go="record"><svg viewBox="0 0 24 24"><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></svg>Record</button>
  <button data-go="coverage"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg>Coverage</button>
  <button data-go="how"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01"/></svg>How it works</button>
</div>

<div class="wrap" id="banners"></div>
<main class="wrap" id="main"><div class="empty"><b>LOADING</b></div></main>

<nav aria-label="Sections"><div class="in">
  <button data-tab="selected"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>Selected</button>
  <button data-tab="goals"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 4.5h-5L8 10z"/><path d="M12 7V3.5M16 10l3.4-1.2M14.5 14.5l2 3M9.5 14.5l-2 3M8 10L4.6 8.8"/></svg>Easy Goals</button>
  <button data-tab="misses"><svg viewBox="0 0 24 24"><path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/></svg>Misses</button>
  <button data-tab="ballon"><svg viewBox="0 0 24 24"><path d="M8 4h8v4a4 4 0 0 1-8 0z"/><path d="M8 5H5a3 3 0 0 0 3 4M16 5h3a3 3 0 0 1-3 4M12 12v4M9 20h6M10 16h4"/></svg>Ballon d'Or</button>
  <button data-tab="btts"><svg viewBox="0 0 24 24"><path d="M7 15a4 4 0 0 1-.5-8 5.5 5.5 0 0 1 10.6 1.5A3.3 3.3 0 0 1 17 15z"/><path d="M8 18l-1 2M12 18l-1 2M16 18l-1 2"/></svg>Raining Goals</button>
</div></nav>

<script>
(function(){
"use strict";
let D = null, COV = null, REC = null;
const TZ = "Europe/Dublin";
async function getJSON(name){
  try { const r = await fetch(`data/${name}?v=${Date.now()}`, {cache: "no-store"}); if (r.ok) return await r.json(); } catch (e) {}
  return (window.__GS__ || {})[name.replace(".json", "")] || null;
}
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = (x, d = 0) => (x * 100).toFixed(d) + "%";
const hue = v => { const t = Math.max(0, Math.min(1, (v - 1) / 99)); return `hsl(${Math.round(t * 128)} 70% ${52 + Math.sin(t * Math.PI) * 6}%)`; };
const tm = ts => new Intl.DateTimeFormat("en-IE", {timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false}).format(new Date(ts * 1000));
const now = () => Date.now() / 1000;
const ago = s => { const m = Math.floor(s / 60); return m < 60 ? `${m} min ago` : `${Math.floor(m / 60)} h ${m % 60} min ago`; };
const odds = p => { const f = 1 / p - 1; return f >= 1 ? `${Math.round(f)}/1` : `1/${Math.round(1 / f)}`; };

const SEC = {
  goals:  {name: "Easy Goals",   blurb: () => `Games most likely to have at least one goal, but no shorter than ${Math.round(D.goals_max * 100)}%.`,
           fig: g => [pct(1 - g.p00, 1), "1+ goals"]},
  misses: {name: "Misses",       blurb: () => `Teams most likely not to win (lose or draw). Underdogs no longer than ${D.misses_longest}/1.`,
           fig: g => [pct(g.sec.misses.p, 0), "not to win"]},
  ballon: {name: "Ballon d'Or",  blurb: () => `Clear favourites (${Math.round(D.ballon_min * 100)}% or more to win), most likely first.`,
           fig: g => [pct(g.sec.ballon.p, 0), "to win"]},
  btts:   {name: "Raining Goals",blurb: () => "Games most likely to see both teams score.",
           fig: g => [pct(g.p_btts, 0), "both score"]},
};
const picks = key => D.games.filter(g => g.sec[key].pick).sort((a, b) => a.sec[key].rank - b.sec[key].rank);
const teamOf = (g, key) => g[g.sec[key].team].name;

const OPEN = new Set();
/* ---------- pieces ---------- */
function chips(g, key){
  const o = [];
  if (g.tags.includes("limited_data")) o.push(`<span class="chip amber">Limited data</span>`);
  if (g.tags.includes("time_tbc")) o.push(`<span class="chip grey">Time TBC</span>`);
  if (g.tags.includes("too_short") && (!key || key === "all")) o.push(`<span class="chip grey">Goals too short</span>`);
  if (g.intl) o.push(`<span class="chip grey">International</span>`);
  return o.join("");
}
function teamsLine(g, key){
  const pk = key === "misses" || key === "ballon" ? g.sec[key].team : null;
  const n = side => `<span class="${pk === side ? "pk" : ""}">${esc(g[side].name)}</span>`;
  return `${n("home")}<span class="v">v</span>${n("away")}`;
}
function subLine(g, key){
  const st = now() >= g.ts;
  return `<span class="tm">${tm(g.ts)}</span>${st ? `<span class="x">✕</span><span>${ago(now() - g.ts)}</span>` : ""}<span>·</span><span class="cp">${esc(g.comp)}</span>${chips(g, key)}`;
}
function rates(t){
  const c = v => `style="color:${hue(v)}"`;
  return `<div class="rt"><span ${c(t.ovr)}>${t.ovr}<i>OVR</i></span><span ${c(t.att)}>${t.att}<i>ATT</i></span><span ${c(t.def)}>${t.def}<i>DEF</i></span></div>`;
}
function details(g, key){
  const extra = {
    goals: `Chance of 0-0 <b>${pct(g.p00, 1)}</b>`,
    misses: `${esc(teamOf(g, "misses"))} to lose or draw <b>${pct(g.sec.misses.p, 1)}</b> · model price for them to win about <b>${odds(1 - g.sec.misses.p)}</b>`,
    ballon: `${esc(teamOf(g, "ballon"))} to win <b>${pct(g.sec.ballon.p, 1)}</b> · model price about <b>${odds(g.sec.ballon.p)}</b>`,
    btts: `${esc(g.home.name)} score <b>${pct(g.p_home_score)}</b> · ${esc(g.away.name)} score <b>${pct(g.p_away_score)}</b>`,
  }[key] || "";
  return `<div class="det ${OPEN.has(key + "-" + g.fid) ? "open" : ""}" data-det="${key}-${g.fid}">
    <div class="wdl"><span style="width:${g.pw_home * 100}%"></span><span style="width:${g.pd * 100}%"></span><span style="width:${g.pw_away * 100}%"></span></div>
    <div class="wdlk"><span>${esc(g.home.name)} ${pct(g.pw_home)}</span><span>Draw ${pct(g.pd)}</span><span>${esc(g.away.name)} ${pct(g.pw_away)}</span></div>
    <div class="tr"><div class="n">${esc(g.home.name)}</div>${rates(g.home)}</div>
    <div class="tr"><div class="n">${esc(g.away.name)}</div>${rates(g.away)}</div>
    <div class="dl">${extra}<br>Expected goals <b>${g.xg_home.toFixed(2)} – ${g.xg_away.toFixed(2)}</b> · ${esc(g.round)}${g.tags.includes("limited_data") ? "<br>Limited data: few results for at least one team, so the score is trimmed slightly." : ""}</div>
  </div>`;
}
function pickRow(g, key){
  const s = g.sec[key], [v, l] = SEC[key].fig(g);
  return `<div class="row" data-open="${key}-${g.fid}">
    <div class="sc" style="color:${hue(s.score)}">${s.score.toFixed(1)}<small>#${s.rank}</small></div>
    <div class="mid"><div class="teams">${teamsLine(g, key)}</div><div class="sub">${subLine(g, key)}</div></div>
    <div class="kf"><b>${v}</b><i>${l}</i></div></div>${details(g, key)}`;
}

/* ---------- next best (below the picks) ---------- */
const nextOpen = {};
function nextBest(key){
  const rest = D.games.filter(g => g.sec[key].listed !== false && !g.sec[key].pick).sort((a, b) => a.sec[key].rank - b.sec[key].rank);
  if (!rest.length) return "";
  const passed = rest.filter(g => g.sec[key].score >= (g.intl ? D.min_intl : D.min_club));
  const below = rest.filter(g => g.sec[key].score < (g.intl ? D.min_intl : D.min_club));
  let h = `<button class="fold ${nextOpen[key] ? "open" : ""}" data-next="${key}"><span>NEXT BEST (${rest.length})</span><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>`;
  if (nextOpen[key]) {
    h += `<div class="panel dim" style="margin-top:8px">`;
    if (passed.length) h += `<div class="gh">Passed the mark, outside the top ${D.top_n}</div>` + passed.map(g => pickRow(g, key)).join("");
    if (below.length) h += `<div class="gh">Below the pass mark: not picks</div>` + below.map(g => pickRow(g, key)).join("");
    h += `</div>`;
  }
  return h;
}

/* ---------- views ---------- */
function sectionView(key){
  const list = picks(key), S = SEC[key];
  let h = `<div class="sh"><h2>${S.name}</h2><p>${S.blurb()}</p>
    <div class="meta">${list.length} pick${list.length === 1 ? "" : "s"} · minimum score ${D.min_club} (internationals ${D.min_intl}) · tap a game for details · next best below</div></div>`;
  if (!list.length) return h + `<div class="note"><b>NO PICKS TODAY</b> &nbsp;No games reached the minimum score.</div>` + nextBest(key);
  h += `<div class="panel">${list.map(g => pickRow(g, key)).join("")}</div>`;
  if (list.length < D.top_n) h += `<div class="note"><b>ONLY ${list.length} PICK${list.length === 1 ? "" : "S"}</b> &nbsp;Only ${list.length} game${list.length === 1 ? "" : "s"} reached the minimum score today, so the list isn't padded with weaker ones.</div>`;
  return h + nextBest(key);
}
function selectedGames(){
  const m = new Map();
  for (const key of ["goals", "misses", "ballon"]) for (const g of picks(key)) {
    if (!m.has(g.fid)) m.set(g.fid, {g, labels: []});
    const lab = key === "goals" ? `Easy Goals #${g.sec.goals.rank}` :
      `${SEC[key].name} #${g.sec[key].rank} · ${teamOf(g, key)}`;
    m.get(g.fid).labels.push(lab);
  }
  return [...m.values()].sort((a, b) => a.g.ts - b.g.ts);
}
function selRow({g, labels}){
  return `<div class="row srow" data-open="sel-${g.fid}">
    <div class="ko">${tm(g.ts)}${now() >= g.ts ? `<small class="x">✕ ${ago(now() - g.ts)}</small>` : ""}</div>
    <div class="mid"><div class="teams">${esc(g.home.name)}<span class="v">v</span>${esc(g.away.name)}</div>
      <div class="sub"><span class="cp">${esc(g.comp)}</span>${chips(g, "sel")}</div>
      <div class="labels">${labels.map(l => `<span class="chip gold">${esc(l)}</span>`).join("")}</div></div></div>${details(g, "sel")}`;
}
let foldOpen = false;
function selectedView(){
  const all = selectedGames(), up = all.filter(x => x.g.ts > now()), st = all.filter(x => x.g.ts <= now());
  let h = `<div class="sh"><h2>Selected games</h2><p>Every pick from Easy Goals, Misses and Ballon d'Or, in kickoff order.</p></div>`;
  if (up.length) {
    const n = up[0].g;
    h += `<div class="count"><div class="k">NEXT KICK-OFF</div><div class="t" id="cd">--:--:--</div>
      <div class="g">${esc(n.home.name)} v ${esc(n.away.name)}</div><div class="m">${tm(n.ts)} · ${esc(n.comp)}</div></div>`;
  }
  h += `<div class="sh" style="padding-top:14px"><div class="meta">${up.length} to come · ${st.length} already started</div></div>`;
  h += up.length ? `<div class="panel">${up.map(selRow).join("")}</div>` : `<div class="note"><b>ALL STARTED</b> &nbsp;Every selected game has kicked off.</div>`;
  if (st.length) {
    h += `<button class="fold ${foldOpen ? "open" : ""}" id="fold"><span>ALREADY STARTED (${st.length})</span><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>`;
    if (foldOpen) h += `<div class="panel" style="margin-top:8px">${st.map(selRow).join("")}</div>`;
  }
  return h;
}
function allView(){
  const comps = [...new Set(D.games.map(g => g.comp))].sort();
  return `<button class="back" data-back><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>BACK</button>
    <div class="sh"><h2>All games</h2><p>Every game in the next 24 hours, with its score in each section.</p></div>
    <div class="controls"><input id="q" placeholder="Search team or competition"><select id="fc"><option value="">All competitions</option>${comps.map(c => `<option>${esc(c)}</option>`).join("")}</select>
    <select id="so"><option value="ko">Sort: kickoff</option><option value="goals">Sort: Easy Goals</option><option value="btts">Sort: Raining Goals</option></select></div>
    <div class="panel" id="allList"></div>`;
}
function allRows(){
  const q = ($("#q")?.value || "").toLowerCase(), fc = $("#fc")?.value || "", so = $("#so")?.value || "ko";
  let l = D.games.filter(g => (!fc || g.comp === fc) && (g.home.name + " " + g.away.name + " " + g.comp).toLowerCase().includes(q));
  l.sort((a, b) => so === "ko" ? a.ts - b.ts : b.sec[so].score - a.sec[so].score);
  const mini = (lab, v) => `<span class="mini" style="color:${hue(v)}"><i>${lab}</i>${v.toFixed(0)}</span>`;
  $("#allList").innerHTML = l.map(g => {
    const w = g.sec.ballon.listed ? ["BD", g.sec.ballon.score] : g.sec.misses.listed ? ["MI", g.sec.misses.score] : null;
    return `<div class="row srow" data-open="all-${g.fid}"><div class="ko">${tm(g.ts)}${now() >= g.ts ? `<small class="x">✕</small>` : ""}</div>
      <div class="mid"><div class="teams">${esc(g.home.name)}<span class="v">v</span>${esc(g.away.name)}</div>
      <div class="sub"><span class="cp">${esc(g.comp)}</span>${chips(g)}</div>
      <div class="minis">${g.sec.goals.listed ? mini("EG", g.sec.goals.score) : `<span class="mini"><i>EG</i>short</span>`}${w ? mini(w[0], w[1]) : ""}${mini("RG", g.sec.btts.score)}</div></div></div>${details(g, "all")}`;
  }).join("");
}
const SECNAME = {goals: "Easy Goals", misses: "Misses", ballon: "Ballon d'Or", btts: "Raining Goals"};
function recordView(){
  const back = `<button class="back" data-back><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>BACK</button>`;
  if (!REC) return back + `<div class="empty"><b>NO RECORD YET</b>Picks are settled the morning after they're made.</div>`;
  const rate = s => { const n = s.won + s.lost; return n ? (s.won / n * 100).toFixed(1) + "%" : "–"; };
  const card = k => { const s = REC.sections[k]; return `<div class="stat"><div class="k">${SECNAME[k]}</div><div class="v">${rate(s.d30)}</div>
    <div class="s">${s.d30.won} of ${s.d30.won + s.d30.lost} picks · last 30 days<br>All time ${rate(s.all)} (${s.all.won + s.all.lost})</div></div>`; };
  let h = back + `<div class="sh"><h2>Record</h2><p>How each section's picks have done. A pick counts once settled; void games don't count.</p></div>
    <div class="stats">${["goals", "misses", "ballon", "btts"].map(card).join("")}</div>`;
  if ((REC.check || []).length) {
    h += `<div class="sh"><h2 style="font-size:12px">Model check</h2><p>Last 90 days: does the model's confidence match what happened?</p></div>
      <div class="panel">${REC.check.map(c => `<div class="kv"><span>${esc(c.label)}</span><b>${c.forecast} forecast · ${c.actual} actual</b></div>`).join("")}</div>`;
  }
  if ((REC.recent || []).length) {
    h += `<div class="sh"><h2 style="font-size:12px">Last 7 days</h2></div>`;
    for (const d of REC.recent) {
      const day = new Intl.DateTimeFormat("en-IE", {timeZone: TZ, weekday: "long", day: "numeric", month: "long"}).format(new Date(d.date + "T12:00:00Z"));
      h += `<div class="daystr">${esc(day)}</div><div class="panel" style="margin-top:6px">` + d.picks.map(p => {
        const team = p.team ? ` · ${esc(p.team === "home" ? p.h : p.a)}` : "";
        const res = p.res === "pending" ? "Pending" : p.res === "void" ? "Void" : `${p.result[0]}–${p.result[1]} ${p.res === "won" ? "✓" : "✕"}`;
        return `<div class="cov"><div class="vb" style="color:${hue(p.score)}">${Math.round(p.score)}</div>
          <div><div class="t">${esc(p.h)} v ${esc(p.a)}</div><div class="m">${SECNAME[p.section]} #${p.rank}${team} · ${esc(p.comp)}</div></div>
          <span class="res ${p.res}">${res}</span></div>`; }).join("") + `</div>`;
    }
  }
  return h;
}
const STATUS = {covered: ["green", "Covered"], partial: ["amber", "Partly covered"], no_games: ["grey", "No games"],
  omitted_budget: ["amber", "Omitted: request limit"], blocked_plan: ["red", "Blocked"], error: ["red", "Error"],
  not_available: ["grey", "Not on free plan"]};
let covProblems = false;
function coverageView(){
  const back = `<button class="back" data-back><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>BACK</button>`;
  if (!COV) return back + `<div class="empty"><b>NO REPORT YET</b></div>`;
  const comps = COV.competitions || [], cnt = {};
  comps.forEach(c => cnt[c.status] = (cnt[c.status] || 0) + 1);
  const ran = COV.generated_utc ? new Date(COV.generated_utc).toLocaleString("en-IE", {timeZone: TZ, dateStyle: "medium", timeStyle: "short"}) : "–";
  let h = back + `<div class="sh"><h2>Coverage</h2><p>This morning's run and what the model has changed.</p></div>
    <div class="panel"><div class="kv"><span>Last run</span><b>${esc(ran)}</b></div>
    <div class="kv"><span>Games scored</span><b>${COV.games_scored ?? "–"}</b></div>
    <div class="kv"><span>Requests used · left this month</span><b>${COV.requests_used} · ${COV.monthly_remaining ?? "–"}</b></div>
    <div class="kv"><span>Competitions with games</span><b>${(cnt.covered || 0) + (cnt.partial || 0)} of ${comps.length}</b></div>
    <div class="kv"><span>Not on free plan</span><b>${cnt.not_available || 0}</b></div>
    <div class="kv"><span>Problems</span><b>${(cnt.omitted_budget || 0) + (cnt.blocked_plan || 0) + (cnt.error || 0)}</b></div>
    <div class="kv"><span>Dropped: postponed / already started</span><b>${COV.dropped_postponed ?? 0} / ${COV.dropped_started ?? 0}</b></div>
    ${COV.last_error ? `<div class="kv"><span>Last error</span><b style="color:var(--red)">${esc(COV.last_error)}</b></div>` : ""}</div>`;
  const md = COV.model || {};
  if ((md.changes || []).length) {
    h += `<div class="sh"><h2 style="font-size:12px">Model adjustments</h2><p>What the daily analysis changed. Recent form counts ${Math.round((md.form_weight || 0) * 100)}%; older games fade with a ${md.half_life} day half-life.</p></div>
      <div class="panel">${md.changes.map(c => `<div class="log">${esc(c.text)}<small>${esc(c.date)}</small></div>`).join("")}</div>`;
  }
  h += `<div class="sh"><h2 style="font-size:12px">Competitions</h2></div>
    <div class="subtabs"><button data-cv="all" class="${covProblems ? "" : "on"}">All ${comps.length}</button><button data-cv="prob" class="${covProblems ? "on" : ""}">Problems only</button></div><div class="panel">`;
  for (const c of comps) {
    if (covProblems && ["covered", "no_games", "not_available"].includes(c.status)) continue;
    const [cls, label] = STATUS[c.status] || ["grey", c.status];
    const detail = c.status === "covered" || c.status === "partial" ? `${c.games} game${c.games === 1 ? "" : "s"}` : "";
    h += `<div class="cov"><div class="vb">${c.value}</div><div><div class="t">${esc(c.name)}${c.newly_found ? ` <span class="chip green">New</span>` : ""}</div>
      <div class="m">${c.note ? esc(c.note) : (c.matched || []).map(m => esc(m.name)).join(", ")}</div></div>
      <div style="text-align:right"><span class="chip ${cls}">${label}</span>${detail ? `<div class="m">${detail}</div>` : ""}</div></div>`;
  }
  return h + `</div>`;
}
function howView(){
  return `<button class="back" data-back><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>BACK</button>
    <div class="sh"><h2>How it works</h2></div><div class="panel prose">
    <h3>The score</h3>Every pick gets a score from 1 to 100 for how unlikely it is to go wrong, on its own section's scale. It isn't a percentage. A game becomes a pick at ${D.min_club} or above (${D.min_intl} for internationals), up to ${D.top_n} per section. Fewer qualify on some days, and lists are never padded. Next best shows the rest.
    <h3>Easy Goals</h3>Goes wrong on a 0-0. Games more than ${Math.round(D.goals_max * 100)}% likely to have a goal are too short to be picks; a game right at ${Math.round(D.goals_max * 100)}% scores 100.
    <h3>Misses and Ballon d'Or</h3>A game goes on only one of the two. Ballon d'Or takes clear favourites (${Math.round(D.ballon_min * 100)}% or more to win). Every other game with an underdog no longer than ${D.misses_longest}/1 can go in Misses, where a 3/1 underdog scores about 50 and a ${D.misses_longest}/1 underdog 100.
    <h3>Raining Goals</h3>Goes wrong if either team fails to score.
    <h3>Team strength</h3>Attack and defence ratings come from every result, adjusted for the opponent and the league, and update every morning. Recent form counts a little extra. National teams use three years of internationals.
    <h3>Learning from results</h3>Every prediction is stored and checked against what happened. Each morning, settings are nudged where the evidence shows the forecasts are off, separately for clubs and internationals. Changes are listed on the Coverage screen.
    <h3>All games</h3>Each game shows its score in every section: EG = Easy Goals, BD = Ballon d'Or, MI = Misses, RG = Raining Goals.
    <h3>Reality check</h3>Scores are a ranking, not a guarantee. At short prices one losing pick can wipe out many winners. The Record screen shows how each section is really doing.</div>`;
}
function banners(){
  const b = [];
  if (D) {
    if (Date.now() - Date.parse(D.generated_utc) > 26 * 3600 * 1000)
      b.push(`<div class="banner stale"><b>OUT OF DATE</b> &nbsp;This list was made ${esc(new Date(D.generated_utc).toLocaleString("en-IE", {timeZone: TZ, dateStyle: "medium", timeStyle: "short"}))}. This morning's update may have failed.</div>`);
    if ((D.new_competitions || []).length)
      b.push(`<div class="banner new"><b>NEW ON OPENFOOTAPI</b> &nbsp;${D.new_competitions.map(esc).join(", ")} now included automatically.</div>`);
  }
  if (COV && COV.last_error) b.push(`<div class="banner stale"><b>UPDATE PROBLEM</b> &nbsp;${esc(COV.last_error)}</div>`);
  $("#banners").innerHTML = b.join("");
}

/* ---------- wiring ---------- */
let tab = "selected", page = null;
function render(){
  const m = $("#main");
  if (!D) { m.innerHTML = `<div class="empty"><b>NO DATA YET</b>The first morning run hasn't finished. Run it from GitHub's Actions tab.</div>`; return; }
  if (page === "all") { m.innerHTML = allView(); allRows(); }
  else if (page === "record") m.innerHTML = recordView();
  else if (page === "coverage") m.innerHTML = coverageView();
  else if (page === "how") m.innerHTML = howView();
  else m.innerHTML = tab === "selected" ? selectedView() : sectionView(tab);
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("on", !page && b.dataset.tab === tab));
  tick();
}
function tick(){
  const el = $("#cd"); if (!el) return;
  const up = selectedGames().filter(x => x.g.ts > now());
  if (!up.length) return;
  let s = Math.max(0, Math.round(up[0].g.ts - now()));
  const days = Math.floor(s / 86400); s -= days * 86400;
  const hh = String(Math.floor(s / 3600)).padStart(2, "0"), mm = String(Math.floor(s % 3600 / 60)).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  el.textContent = `${days ? days + "d " : ""}${hh}:${mm}:${ss}`;
}
setInterval(tick, 1000);
document.querySelector("nav").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; tab = b.dataset.tab; page = null; window.scrollTo(0, 0); render(); });
const menu = on => { $("#sheet").classList.toggle("on", on); $("#scrim").classList.toggle("on", on); };
$("#menuBtn").onclick = () => menu(!$("#sheet").classList.contains("on"));
$("#scrim").onclick = () => menu(false);
$("#sheet").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; page = b.dataset.go; menu(false); window.scrollTo(0, 0); render(); });
document.addEventListener("click", e => {
  if (e.target.closest("[data-back]")) { page = null; render(); return; }
  if (e.target.closest("#fold")) { foldOpen = !foldOpen; render(); return; }
  const cv = e.target.closest("[data-cv]"); if (cv) { covProblems = cv.dataset.cv === "prob"; render(); return; }
  const nb = e.target.closest("[data-next]"); if (nb) { nextOpen[nb.dataset.next] = !nextOpen[nb.dataset.next]; render(); return; }
  const r = e.target.closest("[data-open]");
  if (r) { const d = document.querySelector(`[data-det="${CSS.escape(r.dataset.open)}"]`);
    if (d) { d.classList.toggle("open"); d.classList.contains("open") ? OPEN.add(r.dataset.open) : OPEN.delete(r.dataset.open); } }
});
document.addEventListener("input", e => { if (e.target.id === "q") allRows(); });
document.addEventListener("change", e => { if (e.target.id === "fc" || e.target.id === "so") allRows(); });
setInterval(() => { if (!page || page === "all") { const y = window.scrollY; render(); window.scrollTo(0, y); } }, 60000);
(async function start(){
  [D, COV, REC] = await Promise.all([getJSON("today.json"), getJSON("coverage.json"), getJSON("record.json")]);
  banners();
  render();
})();
if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {});
})();
</script>
</body>
</html>
