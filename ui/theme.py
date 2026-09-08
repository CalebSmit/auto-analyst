# ruff: noqa: E501 - this module is a stylesheet held in a string. Wrapping CSS to a
# hundred columns makes it harder to read, not easier.
"""The design language: colour, type, spacing, and eight components.

**Restraint is the whole idea.** This is a tool people use on a client's numbers on a
Tuesday afternoon. It should look like something the firm paid for and nothing like
something demanding attention: one accent, a small type scale used strictly, generous
space, and hairlines instead of borders. Colour carries meaning - green, amber, red mean
fine, attention, problem - and is used nowhere else, so that when something does turn
amber it reads as information rather than decoration.

**Numbers are the subject.** Every figure is set in tabular numerals so columns line up
and a changing value does not shift the ones beside it, and the large ones are tracked
tighter, which is what makes a number look considered rather than merely big.

**Every surface answers a question.** A card carries a title, a one-line statement of what
it is for, and its content - because the alternative is a table of figures that only makes
sense to whoever built it.
"""

from __future__ import annotations

__all__ = ["CSS", "SHELL", "shell"]

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
 /* Ground and surfaces. Four steps, so depth is layering rather than shadow. */
 --bg:#0b0d10; --surface:#111419; --surface-2:#161a20; --line:#20252d; --line-soft:#191d23;
 /* Ink. Three weights of quiet, one of emphasis. */
 --ink:#e8ebef; --ink-2:#a8b0bb; --ink-3:#6f7883; --ink-4:#4a515b;
 /* One accent, and the three that carry meaning. */
 --accent:#c9a86a; --accent-soft:rgba(201,168,106,.12);
 --link:#7fa9dd;
 --good:#5bbd8a; --good-soft:rgba(91,189,138,.12);
 --warn:#d7a54a; --warn-soft:rgba(215,165,74,.12);
 --bad:#d9727a; --bad-soft:rgba(217,114,122,.12);
 --radius:10px; --radius-sm:6px;
 --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body{font:14px/1.5 var(--sans);margin:0;background:var(--bg);color:var(--ink);
 font-variant-numeric:tabular-nums}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:2px}
.mono{font-family:var(--mono);font-size:12.5px;letter-spacing:-.01em}

/* ---------------------------------------------------------------- chrome */
.top{position:sticky;top:0;z-index:20;background:rgba(11,13,16,.86);
 backdrop-filter:saturate(140%) blur(12px);border-bottom:1px solid var(--line)}
.top-in{max-width:1240px;margin:0 auto;padding:0 24px;height:56px;display:flex;
 align-items:center;gap:20px}
.brand{display:flex;align-items:baseline;gap:9px;margin-right:4px}
.brand b{font-size:14px;font-weight:600;letter-spacing:-.01em}
.brand span{font-size:11px;color:var(--ink-3);letter-spacing:.10em;text-transform:uppercase}
.nav{display:flex;gap:2px;margin-left:8px}
.nav a{padding:6px 11px;border-radius:var(--radius-sm);color:var(--ink-2);font-size:13px}
.nav a:hover{background:var(--surface-2);color:var(--ink);text-decoration:none}
.nav a[aria-current]{background:var(--surface-2);color:var(--ink);
 box-shadow:inset 0 0 0 1px var(--line)}
.top .right{margin-left:auto;display:flex;align-items:center;gap:14px;
 font-size:12.5px;color:var(--ink-3)}

.wrap{max-width:1240px;margin:0 auto;padding:26px 24px 72px}
.page-head{margin:4px 0 22px}
.page-head h1{font-size:21px;font-weight:600;letter-spacing:-.02em;margin:0 0 5px}
.page-head p{margin:0;color:var(--ink-3);font-size:13.5px;max-width:70ch}

.cols{display:grid;gap:16px;align-items:start}
.cols.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.cols.side{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}
@media (max-width:1080px){.cols.two,.cols.side{grid-template-columns:minmax(0,1fr)}}

/* ---------------------------------------------------------------- card */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
 margin-bottom:16px;overflow:hidden}
.card>header{padding:15px 18px 0}
.card h2{font-size:13px;font-weight:600;letter-spacing:-.005em;margin:0}
.card .why{margin:4px 0 0;font-size:12.5px;color:var(--ink-3);max-width:66ch}
.card .body{padding:13px 18px 16px}
.card .foot{padding:11px 18px;border-top:1px solid var(--line-soft);
 background:var(--surface-2);display:flex;gap:8px;align-items:center;flex-wrap:wrap}

/* ---------------------------------------------------------------- metric */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;
 background:var(--line);border:1px solid var(--line);border-radius:var(--radius);
 overflow:hidden}
.metric{background:var(--surface);padding:15px 17px 16px}
.metric .k{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3);
 display:block;margin-bottom:9px}
.metric .v{font-size:27px;font-weight:600;letter-spacing:-.03em;line-height:1.05;
 display:block;color:var(--ink)}
.metric .v small{font-size:14px;font-weight:500;color:var(--ink-3);letter-spacing:-.01em}
.metric .c{display:block;margin-top:7px;font-size:12px;color:var(--ink-3)}
.metric.good .v{color:var(--good)}.metric.warn .v{color:var(--warn)}.metric.bad .v{color:var(--bad)}

/* ---------------------------------------------------------------- rows */
.rows{display:flex;flex-direction:column}
.r{display:flex;align-items:baseline;gap:12px;padding:9px 0;
 border-bottom:1px solid var(--line-soft)}
.r:last-child{border-bottom:0}
.r .lbl{flex:1;min-width:0;color:var(--ink-2)}
.r .lbl b{color:var(--ink);font-weight:500}
.r .val{font-weight:600;white-space:nowrap}
.r .sub{color:var(--ink-3);font-size:12.5px;white-space:nowrap}
.r.head{padding-bottom:6px;border-bottom:1px solid var(--line)}
.r.head span{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-4);
 font-weight:500}
.r.link{cursor:pointer;border-radius:var(--radius-sm);padding-left:8px;padding-right:8px;
 margin:0 -8px}
.r.link:hover{background:var(--surface-2)}

/* ---------------------------------------------------------------- pill */
.pill{display:inline-flex;align-items:center;gap:6px;padding:2.5px 9px;border-radius:99px;
 font-size:11.5px;font-weight:500;letter-spacing:.005em;white-space:nowrap;
 background:var(--surface-2);color:var(--ink-2);box-shadow:inset 0 0 0 1px var(--line)}
.pill.good{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px rgba(91,189,138,.24)}
.pill.warn{background:var(--warn-soft);color:var(--warn);box-shadow:inset 0 0 0 1px rgba(215,165,74,.24)}
.pill.bad{background:var(--bad-soft);color:var(--bad);box-shadow:inset 0 0 0 1px rgba(217,114,122,.26)}
.pill.accent{background:var(--accent-soft);color:var(--accent);box-shadow:inset 0 0 0 1px rgba(201,168,106,.26)}
.dot{width:6px;height:6px;border-radius:99px;background:currentColor;flex:none}

/* ---------------------------------------------------------------- bar */
.bar{height:5px;border-radius:99px;background:var(--surface-2);overflow:hidden;
 box-shadow:inset 0 0 0 1px var(--line-soft)}
.bar>i{display:block;height:100%;background:var(--accent);border-radius:99px;
 transition:width .45s cubic-bezier(.4,0,.2,1)}
.bar.good>i{background:var(--good)}.bar.warn>i{background:var(--warn)}
.bar.bad>i{background:var(--bad)}

/* ---------------------------------------------------------------- controls */
button{font:500 12.5px/1 var(--sans);background:var(--surface-2);color:var(--ink);
 border:1px solid var(--line);border-radius:var(--radius-sm);padding:7px 12px;cursor:pointer;
 transition:background .12s ease,border-color .12s ease}
button:hover{background:#1d222a;border-color:#2b323c}
button:active{transform:translateY(.5px)}
button.primary{background:var(--accent);color:#241c0c;border-color:transparent;font-weight:600}
button.primary:hover{background:#d6b678}
button.quiet{background:transparent;border-color:transparent;color:var(--ink-3);padding:6px 8px}
button.quiet:hover{color:var(--ink);background:var(--surface-2)}
button:disabled{opacity:.45;cursor:not-allowed}
input,textarea,select{font:13px var(--sans);background:var(--bg);color:var(--ink);
 border:1px solid var(--line);border-radius:var(--radius-sm);padding:8px 10px;width:100%;
 margin:0 0 8px;outline:none;transition:border-color .12s ease,box-shadow .12s ease}
input:focus,textarea:focus,select:focus{border-color:#3a434f;box-shadow:0 0 0 3px rgba(201,168,106,.10)}
input::placeholder{color:var(--ink-4)}
label{display:block;font-size:11.5px;color:var(--ink-3);margin:0 0 4px;letter-spacing:.01em}
select{width:auto;padding:5px 9px;margin:0}

/* ---------------------------------------------------------------- states */
.empty{padding:22px 4px;text-align:center;color:var(--ink-3);font-size:13px}
.empty b{display:block;color:var(--ink-2);font-weight:500;margin-bottom:4px}
.note{font-size:12.5px;color:var(--ink-3);margin-top:10px;line-height:1.55}
.skel{height:11px;border-radius:4px;background:linear-gradient(90deg,var(--surface-2),#1c212a,var(--surface-2));
 background-size:200% 100%;animation:sh 1.3s ease-in-out infinite;margin:9px 0}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ---------------------------------------------------------------- toast */
#toast{position:fixed;left:50%;bottom:26px;transform:translate(-50%,14px);z-index:60;
 max-width:min(680px,92vw);padding:11px 16px;border-radius:var(--radius);
 background:var(--surface-2);border:1px solid var(--line);color:var(--ink);font-size:13px;
 box-shadow:0 12px 34px rgba(0,0,0,.5);opacity:0;pointer-events:none;
 transition:opacity .18s ease,transform .18s ease}
#toast.on{opacity:1;transform:translate(-50%,0)}
#toast.bad{border-color:rgba(217,114,122,.4)}
#toast.good{border-color:rgba(91,189,138,.32)}
#toast .code{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);display:block;margin-top:3px}

/* ---------------------------------------------------------------- steps */
.steps{display:flex;flex-direction:column;gap:2px}
.step{display:flex;gap:12px;align-items:flex-start;padding:10px 10px;border-radius:var(--radius-sm)}
.step.now{background:var(--accent-soft);box-shadow:inset 0 0 0 1px rgba(201,168,106,.22)}
.step .mark{width:19px;height:19px;border-radius:99px;flex:none;margin-top:1px;
 display:grid;place-items:center;font-size:11px;font-weight:600;
 background:var(--surface-2);color:var(--ink-4);box-shadow:inset 0 0 0 1px var(--line)}
.step.done .mark{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px rgba(91,189,138,.3)}
.step.now .mark{background:var(--accent);color:#241c0c;box-shadow:none}
.step .t{font-size:13px;color:var(--ink)}
.step.done .t{color:var(--ink-3)}
.step .d{font-size:12.5px;color:var(--ink-3);margin-top:2px}
.step .go{margin-left:auto}

/* ---------------------------------------------------------------- node map */
.map-groups{display:flex;flex-direction:column;gap:11px}
.map-group>h3{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-4);
 margin:0 0 6px;font-weight:500}
.map{display:flex;flex-wrap:wrap;gap:4px}
.node{display:inline-flex;align-items:center;gap:6px;padding:4px 9px;border-radius:var(--radius-sm);
 font-size:11.5px;line-height:1.3;background:transparent;color:var(--ink-4);
 box-shadow:inset 0 0 0 1px var(--line-soft);cursor:default;transition:background .15s ease}
.node .id{font-family:var(--mono);font-size:11px}
.node[title]{cursor:help}
.node.used{color:var(--ink-2);background:var(--surface-2);box-shadow:inset 0 0 0 1px var(--line)}
.node.passed{color:var(--good);background:var(--good-soft);box-shadow:inset 0 0 0 1px rgba(91,189,138,.26)}
.node.failed{color:var(--bad);background:var(--bad-soft);box-shadow:inset 0 0 0 1px rgba(217,114,122,.34);font-weight:500}
.node.active{color:var(--accent);background:var(--accent-soft);box-shadow:inset 0 0 0 1px rgba(201,168,106,.34)}
.node .ring{width:9px;height:9px;border-radius:99px;flex:none;
 border:1.5px solid currentColor;border-top-color:transparent;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 12px;font-size:11.5px;color:var(--ink-3)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{width:8px;height:8px;border-radius:2px;display:inline-block}
.diag{margin-top:12px}
.diag .d-row{padding:9px 11px;border-radius:var(--radius-sm);background:var(--bad-soft);
 box-shadow:inset 0 0 0 1px rgba(217,114,122,.24);margin-bottom:6px}
.diag .d-row .code{font-family:var(--mono);font-size:11.5px;color:var(--bad);font-weight:500}
.diag .d-row .msg{display:block;margin-top:3px;color:var(--ink-2);font-size:12.5px}

details>summary{cursor:pointer;color:var(--ink-3);font-size:12.5px;list-style:none;
 padding:4px 0;user-select:none}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"›";display:inline-block;margin-right:7px;
 transition:transform .15s ease;color:var(--ink-4)}
details[open]>summary::before{transform:rotate(90deg)}
details>summary:hover{color:var(--ink-2)}
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
