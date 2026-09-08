# ruff: noqa: E501 - this module is a stylesheet held in a string. Wrapping CSS to a
# hundred columns makes it harder to read, not easier.
"""The design language: Chartwell's colours and type, one screen per page, nine components.

**The palette is the firm's, not ours.** Every colour below is a token from the brand
sheet (`Chartwell Templates/shared/brand.css`, which mirrors the brand guidelines) or a
mix of two of them. Deep Navy carries the masthead and the headlines, Steel Blue is the
one accent, and gold appears exactly where the guidelines say it may - sparingly: a
hairline under the masthead and the mark on the current tab. Meaning is carried by three
of the firm's own colours rather than a traffic light: Mint Mist for *fine*, gold for
*attention*, Deep Plum for *problem* - so that when something turns plum it reads as
information rather than as an alarm somebody bolted on.

**Georgia for what is read, Calibri for what is counted.** Headlines and titles are set in
the brand's serif; the body, every figure and every table in the brand's sans, with
tabular lining numerals so columns line up and a changing value does not shift the ones
beside it. That is what makes a number look considered rather than merely big.

**One screen.** The page never scrolls. The masthead, the page line and a board of panels
fill the viewport exactly; a panel whose content is longer than its share scrolls inside
itself, and the type scale is fluid so a 13-inch laptop and a 27-inch monitor both get the
whole board. This is a tool read standing up while a run goes: the thing you need is on
screen, not below the fold.

**Every surface answers a question.** A panel carries a title, a one-line statement of
what it is for, and its content - because the alternative is a table of figures that only
makes sense to whoever built it.
"""

from __future__ import annotations

__all__ = ["CSS", "SHELL", "shell"]

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
 /* Chartwell brand tokens. Values mirror chartwell_brand_guidelines/color_scheme.md. */
 --brand-p1:#0c2e3f; --brand-p2:#4f758b; --brand-p3:#89b2c4; --brand-p4:#c8dfd8;
 --brand-s1:#000000; --brand-s2:#512a44; --brand-s3:#c19b2b; --brand-s4:#414042; --brand-s5:#e5dec2;
 --brand-n1:#81827e; --brand-n2:#8d8d87; --brand-n3:#e7e6dd;
 --brand-font-headline:Georgia,"Times New Roman",Times,serif;
 --brand-font-body:Calibri,Candara,"Segoe UI",sans-serif;

 /* Ground and surfaces: paper, and white panels on it. Depth is layering, not shadow. */
 --bg:color-mix(in srgb,var(--brand-n3) 55%,white);
 --surface:#ffffff;
 --surface-2:color-mix(in srgb,var(--brand-n3) 42%,white);
 --line:color-mix(in srgb,var(--brand-p3) 34%,var(--brand-n3));
 --line-soft:color-mix(in srgb,var(--brand-n3) 72%,white);
 /* Ink. Navy for what is read first, grey for the rest, three weights of quiet. */
 --navy:var(--brand-p1);
 --ink:var(--brand-s4);
 --ink-2:color-mix(in srgb,var(--brand-s4) 72%,var(--brand-n1));
 --ink-3:var(--brand-n1);
 --ink-4:color-mix(in srgb,var(--brand-n2) 72%,var(--brand-n3));
 /* One accent, one for links, and the three that carry meaning. */
 --accent:var(--brand-p2); --accent-soft:color-mix(in srgb,var(--brand-p2) 11%,white);
 --gold:var(--brand-s3);
 --link:var(--brand-p2);
 --good:color-mix(in srgb,var(--brand-p4) 40%,var(--brand-p1)); --good-soft:color-mix(in srgb,var(--brand-p4) 48%,white);
 --warn:color-mix(in srgb,var(--brand-s3) 78%,var(--brand-s4)); --warn-soft:color-mix(in srgb,var(--brand-s3) 14%,white);
 --bad:var(--brand-s2); --bad-soft:color-mix(in srgb,var(--brand-s2) 9%,white);
 --radius:6px; --radius-sm:4px;
 --serif:var(--brand-font-headline);
 --sans:var(--brand-font-body);
 --mono:Consolas,"Cascadia Mono",ui-monospace,Menlo,monospace;
 --shadow:0 1px 0 rgba(12,46,63,.04),0 1px 2px rgba(12,46,63,.05);
}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
 /* Fluid: the whole board fits a 13-inch laptop and a 27-inch monitor alike. */
 font-size:clamp(12px,.55vw + 5.5px,14.5px);height:100%;overflow:hidden}
body{font:1rem/1.45 var(--sans);margin:0;height:100%;overflow:hidden;
 background:var(--bg);color:var(--ink);display:flex;flex-direction:column;
 font-variant-numeric:lining-nums tabular-nums}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:2px}
b,strong{font-weight:600}
.mono{font-family:var(--mono);font-size:.88em;letter-spacing:-.01em}
*{scrollbar-width:thin;scrollbar-color:var(--brand-p3) transparent}
*::-webkit-scrollbar{width:8px;height:8px}
*::-webkit-scrollbar-thumb{background:var(--brand-p3);border-radius:99px;border:2px solid transparent;background-clip:padding-box}
*::-webkit-scrollbar-track{background:transparent}

/* ---------------------------------------------------------------- masthead */
.top{flex:none;background:var(--navy);color:var(--brand-s5);
 border-bottom:1px solid var(--gold);box-shadow:0 1px 0 color-mix(in srgb,var(--navy) 18%,transparent)}
.top-in{padding:0 1.6rem;height:3.4rem;display:flex;align-items:center;gap:1.4rem}
.brand{display:flex;align-items:baseline;gap:.7rem;margin-right:.4rem}
.brand b{font:400 1.2rem/1 var(--serif);letter-spacing:.005em;color:white}
.brand span{font-size:.7rem;color:var(--brand-p3);letter-spacing:.2em;text-transform:uppercase}
.nav{display:flex;gap:.15rem;margin-left:.6rem;align-self:stretch}
.nav a{display:flex;align-items:center;padding:0 .8rem;color:color-mix(in srgb,var(--brand-s5) 78%,var(--brand-p3));
 font-size:.95rem;letter-spacing:.01em;border-bottom:2px solid transparent;margin-bottom:-1px;
 transition:color .12s ease}
.nav a:hover{color:white;text-decoration:none}
.nav a[aria-current]{color:white;border-bottom-color:var(--gold)}
.top .right{margin-left:auto;display:flex;align-items:center;gap:1rem;
 font-size:.86rem;color:var(--brand-p3)}
.top .right b{color:var(--brand-s5);font-weight:600}
.top .pill{background:transparent;color:var(--brand-s5);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand-p3) 55%,transparent)}
.top .pill.warn{color:var(--gold);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--gold) 55%,transparent)}

/* ---------------------------------------------------------------- page */
.wrap{flex:1;min-height:0;display:flex;flex-direction:column;gap:.8rem;padding:.9rem 1.6rem 1rem}
.page-head{flex:none;display:flex;align-items:baseline;gap:1.1rem;flex-wrap:wrap;
 padding:0 .1rem .1rem;border-bottom:1px solid var(--line);padding-bottom:.55rem}
.page-head h1{font:400 1.55rem/1.1 var(--serif);letter-spacing:-.005em;margin:0;color:var(--navy)}
.page-head p{margin:0;color:var(--ink-3);font-size:.92rem;flex:1;min-width:20ch}
.page-head .tools{margin-left:auto;display:flex;align-items:center;gap:.6rem}

/* The board: a grid that fills the rest of the screen. Each page names its areas. */
.board{flex:1;min-height:0;display:grid;gap:.8rem}
.board>.card{margin:0;min-height:0}

/* Legacy flow layout, kept for anything rendered outside a board. */
.cols{display:grid;gap:.8rem;align-items:start}
.cols.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.cols.side{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}

/* ---------------------------------------------------------------- card */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
 box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0;overflow:hidden}
.card>header{flex:none;padding:.75rem 1rem 0}
.card h2{font:400 1.08rem/1.2 var(--serif);margin:0;color:var(--navy)}
.card h2 small{font:400 .8rem var(--sans);color:var(--ink-3);margin-left:.5rem}
.card .why{margin:.2rem 0 0;font-size:.84rem;color:var(--ink-3);line-height:1.35}
.card .body{flex:1;min-height:0;overflow:auto;padding:.6rem 1rem .8rem}
.card .foot{flex:none;padding:.55rem 1rem;border-top:1px solid var(--line-soft);
 background:var(--surface-2);display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}

/* ---------------------------------------------------------------- metric */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:1px;
 background:var(--line);border:1px solid var(--line);border-radius:var(--radius);
 overflow:hidden;box-shadow:var(--shadow)}
.metric{background:var(--surface);padding:.7rem .95rem .75rem}
.metric .k{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
 display:block;margin-bottom:.35rem}
.metric .v{font-size:1.9rem;font-weight:600;letter-spacing:-.02em;line-height:1.05;
 display:block;color:var(--navy)}
.metric .v small{font-size:.95rem;font-weight:500;color:var(--ink-3);letter-spacing:0}
.metric .c{display:block;margin-top:.3rem;font-size:.82rem;color:var(--ink-3)}
.metric.good .v{color:var(--good)}.metric.warn .v{color:var(--warn)}.metric.bad .v{color:var(--bad)}

/* ---------------------------------------------------------------- rows */
.rows{display:flex;flex-direction:column}
.r{display:flex;align-items:baseline;gap:.8rem;padding:.5rem 0;
 border-bottom:1px solid var(--line-soft)}
.r:last-child{border-bottom:0}
.r .lbl{flex:1;min-width:0;color:var(--ink-2)}
.r .lbl b{color:var(--navy);font-weight:600}
.r .val{font-weight:600;white-space:nowrap;color:var(--navy)}
.r .sub{color:var(--ink-3);font-size:.86rem;white-space:nowrap}
.r .d{display:block;color:var(--ink-3);font-size:.84rem;margin-top:.1rem;white-space:normal}
.r.head{padding-bottom:.35rem;border-bottom:1px solid var(--line)}
.r.head span{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
 font-weight:600}
.r.link{cursor:pointer;border-radius:var(--radius-sm);padding-left:.5rem;padding-right:.5rem;
 margin:0 -.5rem}
.r.link:hover{background:var(--surface-2)}
.r.link.on{background:var(--accent-soft);box-shadow:inset 2px 0 0 var(--accent)}

/* ---------------------------------------------------------------- pill */
.pill{display:inline-flex;align-items:center;gap:.4rem;padding:.12rem .6rem;border-radius:99px;
 font-size:.78rem;font-weight:600;letter-spacing:.02em;white-space:nowrap;
 background:var(--surface-2);color:var(--ink-2);box-shadow:inset 0 0 0 1px var(--line)}
.pill.good{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand-p4) 80%,var(--brand-p2))}
.pill.warn{background:var(--warn-soft);color:var(--warn);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--gold) 45%,white)}
.pill.bad{background:var(--bad-soft);color:var(--bad);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--bad) 30%,white)}
.pill.accent{background:var(--accent-soft);color:var(--accent);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--accent) 38%,white)}
.dot{width:.4rem;height:.4rem;border-radius:99px;background:currentColor;flex:none}

/* ---------------------------------------------------------------- bar */
.bar{height:.34rem;border-radius:99px;background:var(--surface-2);overflow:hidden;
 box-shadow:inset 0 0 0 1px var(--line-soft)}
.bar>i{display:block;height:100%;background:var(--accent);border-radius:99px;
 transition:width .45s cubic-bezier(.4,0,.2,1)}
.bar.good>i{background:var(--good)}.bar.warn>i{background:var(--gold)}
.bar.bad>i{background:var(--bad)}

/* ---------------------------------------------------------------- controls */
button,.btn{font:600 .84rem/1 var(--sans);background:var(--surface);color:var(--navy);
 border:1px solid color-mix(in srgb,var(--brand-p2) 45%,var(--line));border-radius:var(--radius-sm);
 padding:.45rem .8rem;cursor:pointer;letter-spacing:.01em;
 transition:background .12s ease,border-color .12s ease,color .12s ease}
button:hover,.btn:hover{background:var(--accent-soft);border-color:var(--accent)}
button:active{transform:translateY(.5px)}
button.primary{background:var(--navy);color:var(--brand-s5);border-color:var(--navy)}
button.primary:hover{background:color-mix(in srgb,var(--navy) 84%,var(--brand-p2));border-color:transparent}
button.quiet{background:transparent;border-color:transparent;color:var(--accent);padding:.4rem .5rem}
button.quiet:hover{color:var(--navy);background:var(--accent-soft)}
button.ghost{background:transparent;color:var(--ink-2)}
button.small{padding:.28rem .55rem;font-size:.76rem}
button:disabled{opacity:.45;cursor:not-allowed}
input,textarea,select{font:.95rem var(--sans);background:var(--surface);color:var(--ink);
 border:1px solid var(--line);border-radius:var(--radius-sm);padding:.45rem .6rem;width:100%;
 margin:0 0 .55rem;outline:none;transition:border-color .12s ease,box-shadow .12s ease}
input:focus,textarea:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
input::placeholder{color:var(--ink-4)}
label{display:block;font-size:.76rem;color:var(--ink-3);margin:0 0 .2rem;letter-spacing:.06em;text-transform:uppercase}
select{width:auto;padding:.3rem .5rem;margin:0}

/* ---------------------------------------------------------------- states */
.empty{padding:1.2rem .3rem;text-align:center;color:var(--ink-3);font-size:.9rem}
.empty b{display:block;color:var(--navy);font:400 1rem var(--serif);margin-bottom:.2rem}
.note{font-size:.84rem;color:var(--ink-3);margin-top:.6rem;line-height:1.45}
.skel{height:.7rem;border-radius:3px;background:linear-gradient(90deg,var(--surface-2),var(--line-soft),var(--surface-2));
 background-size:200% 100%;animation:sh 1.3s ease-in-out infinite;margin:.6rem 0}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ---------------------------------------------------------------- toast */
#toast{position:fixed;left:50%;bottom:1.6rem;transform:translate(-50%,14px);z-index:60;
 max-width:min(680px,92vw);padding:.7rem 1.1rem;border-radius:var(--radius);
 background:var(--navy);border-top:2px solid var(--gold);color:var(--brand-s5);font-size:.92rem;
 box-shadow:0 12px 34px rgba(12,46,63,.28);opacity:0;pointer-events:none;
 transition:opacity .18s ease,transform .18s ease}
#toast.on{opacity:1;transform:translate(-50%,0)}
#toast.bad{border-top-color:var(--brand-s2);background:color-mix(in srgb,var(--brand-s2) 80%,var(--navy))}
#toast.good{border-top-color:var(--brand-p4)}
#toast .code{font-family:var(--mono);font-size:.8rem;color:var(--brand-p3);display:block;margin-top:.2rem}

/* ---------------------------------------------------------------- modal */
.modal{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;
 background:color-mix(in srgb,var(--navy) 42%,transparent);padding:2rem}
.modal>.card{width:min(56rem,100%);max-height:100%;box-shadow:0 24px 60px rgba(12,46,63,.35)}

/* ---------------------------------------------------------------- steps */
.steps{display:flex;flex-direction:column;gap:.1rem}
.step{display:flex;gap:.7rem;align-items:flex-start;padding:.5rem .55rem;border-radius:var(--radius-sm)}
.step.now{background:var(--accent-soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--accent) 30%,white)}
.step .mark{width:1.35rem;height:1.35rem;border-radius:99px;flex:none;margin-top:.05rem;
 display:grid;place-items:center;font-size:.74rem;font-weight:600;
 background:var(--surface-2);color:var(--ink-3);box-shadow:inset 0 0 0 1px var(--line)}
.step.done .mark{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand-p4) 80%,var(--brand-p2))}
.step.now .mark{background:var(--navy);color:var(--brand-s5);box-shadow:none}
.step>span:not(.mark):not(.go){flex:1;min-width:0}
.step .t{display:block;font-size:.95rem;color:var(--navy);font-weight:600}
.step.done .t{color:var(--ink-3);font-weight:500}
.step .d{display:block;font-size:.84rem;color:var(--ink-3);margin-top:.05rem}
.step .go{margin-left:auto}

/* ---------------------------------------------------------------- node map */
.map-groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));gap:.6rem .9rem}
.map-group>h3{font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
 margin:0 0 .3rem;font-weight:600}
.map{display:flex;flex-wrap:wrap;gap:.22rem}
.node{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .5rem;border-radius:var(--radius-sm);
 font-size:.76rem;line-height:1.3;background:transparent;color:var(--ink-4);
 box-shadow:inset 0 0 0 1px var(--line-soft);cursor:default;transition:background .15s ease}
.node .id{font-family:var(--mono);font-size:.74rem}
.node[title]{cursor:help}
.node.used{color:var(--ink-2);background:var(--surface-2);box-shadow:inset 0 0 0 1px var(--line)}
.node.passed{color:var(--good);background:var(--good-soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--brand-p4) 80%,var(--brand-p2))}
.node.failed{color:var(--bad);background:var(--bad-soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--bad) 35%,white);font-weight:600}
.node.active{color:var(--accent);background:var(--accent-soft);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--accent) 45%,white)}
.node .ring{width:.55rem;height:.55rem;border-radius:99px;flex:none;
 border:1.5px solid currentColor;border-top-color:transparent;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.legend{display:flex;gap:.9rem;flex-wrap:wrap;margin:0 0 .6rem;font-size:.78rem;color:var(--ink-3)}
.legend span{display:inline-flex;align-items:center;gap:.35rem}
.legend i{width:.55rem;height:.55rem;border-radius:2px;display:inline-block}
.diag{margin-top:.6rem}
.diag .d-row{padding:.5rem .7rem;border-radius:var(--radius-sm);background:var(--bad-soft);
 box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--bad) 25%,white);margin-bottom:.35rem}
.diag .d-row .code{font-family:var(--mono);font-size:.8rem;color:var(--bad);font-weight:600}
.diag .d-row .msg{display:block;margin-top:.15rem;color:var(--ink-2);font-size:.86rem}

details>summary{cursor:pointer;color:var(--ink-3);font-size:.86rem;list-style:none;
 padding:.25rem 0;user-select:none}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"\\203A";display:inline-block;margin-right:.45rem;
 transition:transform .15s ease;color:var(--ink-4)}
details[open]>summary::before{transform:rotate(90deg)}
details>summary:hover{color:var(--navy)}
"""

SHELL = """<script>
// The three things every page does: escape, format, and say what happened.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pct = v => (v === null || v === undefined)
  ? '<span style="color:var(--ink-4)">not yet</span>' : (v * 100).toFixed(1) + '%';
const num = (v, dash = 'not yet') => (v === null || v === undefined)
  ? '<span style="color:var(--ink-4)">' + dash + '</span>' : esc(v);
const plural = (n, one, many) => n + ' ' + (n === 1 ? one : many);

let toastTimer = null;
function say(message, kind, code) {
  const box = $('toast');
  if (!box) return;
  box.className = kind || '';
  box.innerHTML = esc(message) + (code ? '<span class="code">' + esc(code) + '</span>' : '');
  box.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove('on'), kind === 'bad' ? 9000 : 3800);
}

// A refusal is a diagnostic the person can act on, not a status code.
async function refusal(response) {
  try {
    const body = await response.json();
    const d = ((body.detail || {}).refused || [])[0];
    if (d) return { text: d.what_now || d.detail, code: d.code + ' — ' + d.detail };
    return { text: typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail) };
  } catch (e) {
    return { text: response.status + ' ' + response.statusText };
  }
}
async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw await refusal(r);
  return r.json();
}
async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body)
  });
  if (!r.ok) throw await refusal(r);
  return r.json();
}
async function act(run, done) {
  try { await run(); say(done, 'good'); await refresh(); }
  catch (e) { say(e.text || String(e), 'bad', e.code); }
}
</script>"""


def shell(title: str, current: str) -> str:
    """The page chrome: one navigation, so the three surfaces are one product.

    `current` is the path of the page being rendered, which marks its own tab. A page that
    does not know which one it is leaves somebody hunting for where they are.
    """
    tabs = (
        ("/admin", "Setup"),
        ("/", "Activity"),
        ("/analytics", "Analytics"),
    )
    links = "".join(
        f'<a href="{path}"{" aria-current=\'page\'" if path == current else ""}>{label}</a>'
        for path, label in tabs
    )
    return (
        f'<header class="top"><div class="top-in">'
        f'<span class="brand"><b>Automated Analyst</b><span>Chartwell</span></span>'
        f'<nav class="nav">{links}</nav>'
        f'<span class="right" id="chrome-right"></span>'
        f"</div></header>"
    )
