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

**Two scales, and nothing off them.** Spacing is `--s1` to `--s7` and type is `--t-label`
to `--t-display`; a value chosen by eye instead is the difference between a page that reads
as composed and one that reads as assembled. A page may not define a colour or a type size
of its own, and a size in pixels would not follow the fluid root the rest of the tool is
set from. Tests hold both.

**Ink is measured, not chosen.** Body text sits at 12:1 against the paper, secondary at 7:1
and the quiet grey at 4.6:1 - the floor for normal text, not a preference. `--ink-4` is
below it on purpose and is for a placeholder, a disabled control or a node no run reached;
nothing a person has to read is set in it. The contrast of every one of them is computed in
the tests rather than asserted here, because "it looks legible" is how it stopped being.

**Emphasis is spent, not sprayed.** The map draws 118 nodes and a run touches eight, so the
ones it did not touch are named rather than drawn - no chip, no border. A diagnostic is a
rule beside the text rather than a pink wash behind it. A figure carries more weight than
its label. A pill is a wash, a hairline and a dot, because a row of saturated badges is the
thing that makes a tool look like a toy.
"""

from __future__ import annotations

__all__ = ["CSS", "SHELL", "shell"]

CSS = r"""
*,*::before,*::after{box-sizing:border-box}
:root{
 /* Chartwell brand tokens. Values mirror chartwell_brand_guidelines/color_scheme.md. */
 --brand-p1:#0c2e3f; --brand-p2:#4f758b; --brand-p3:#89b2c4; --brand-p4:#c8dfd8;
 --brand-s1:#000000; --brand-s2:#512a44; --brand-s3:#c19b2b; --brand-s4:#414042; --brand-s5:#e5dec2;
 --brand-n1:#81827e; --brand-n2:#8d8d87; --brand-n3:#e7e6dd;
 --brand-font-headline:Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif;
 --brand-font-body:Calibri,Candara,"Segoe UI",system-ui,sans-serif;

 /* Spacing. One scale, eight steps, and nothing off it - the reason a page reads as
    composed rather than assembled is that every gap is one of these. */
 --s1:.25rem; --s2:.5rem; --s3:.75rem; --s4:1rem; --s5:1.25rem; --s6:1.75rem; --s7:2.5rem;

 /* Type. Set from the ratio rather than chosen per element: a display size that can
    carry a page, two title sizes, one body, and two quiet ones under it. */
 --t-display:1.75rem; --t-title:1.12rem; --t-subtitle:1rem;
 --t-body:.95rem; --t-sm:.86rem; --t-xs:.79rem; --t-label:.68rem;

 /* Ground and surfaces: warm paper, white panels on it. */
 --bg:#f2f1ea;
 --surface:#ffffff;
 --surface-2:#f7f6f1;
 --surface-sunken:#f1f0ea;
 /* Hairlines are navy at low opacity rather than grey: they sit under the palette
    instead of beside it, which is most of why a rule reads as drawn and not as left over. */
 --line:rgba(12,46,63,.14);
 --line-soft:rgba(12,46,63,.08);
 --line-strong:rgba(12,46,63,.22);

 /* Ink. Four weights, each one measured against the paper it sits on: body text at
    12:1, secondary at 7:1, quiet at 4.6:1 - the last is the floor, not a preference. */
 --navy:var(--brand-p1);
 --ink:#2a2e30;
 --ink-2:#4b5356;
 --ink-3:#696f71;
 --ink-4:#949a9b;

 /* One accent. The darker mix is for text, the lighter for fills and rings, because a
    colour that is legible as a word is rarely the one that is right as a wash. */
 --accent:#4f758b; --accent-ink:#3d5f74;
 --accent-soft:#eef3f6; --accent-line:rgba(79,117,139,.28);
 --link:var(--accent-ink);
 --gold:var(--brand-s3); --gold-ink:#806713;
 --good:#2f6b62; --good-soft:#eef5f2; --good-line:rgba(47,107,98,.26);
 --warn:var(--gold-ink); --warn-soft:#faf5e7; --warn-line:rgba(193,155,43,.34);
 --bad:var(--brand-s2); --bad-soft:#f7eff4; --bad-line:rgba(81,42,68,.22);

 --radius:10px; --radius-sm:6px; --radius-xs:4px;
 --serif:var(--brand-font-headline);
 --sans:var(--brand-font-body);
 --mono:Consolas,"Cascadia Mono",ui-monospace,Menlo,monospace;

 /* Elevation, tinted navy rather than black - a grey shadow on warm paper is what makes
    a panel look printed on top of the page instead of resting on it. */
 --shadow:0 1px 1px rgba(12,46,63,.04),0 2px 6px -2px rgba(12,46,63,.07);
 --shadow-lift:0 1px 1px rgba(12,46,63,.05),0 6px 16px -6px rgba(12,46,63,.14);
 --shadow-modal:0 24px 64px -12px rgba(12,46,63,.32),0 2px 8px rgba(12,46,63,.12);
 --ease:cubic-bezier(.32,.72,0,1);
}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
 /* Fluid: the whole board fits a 13-inch laptop and a 27-inch monitor alike. */
 font-size:clamp(12px,.55vw + 5.5px,14.5px);height:100%;overflow:hidden}
body{font:var(--t-body)/1.5 var(--sans);margin:0;height:100%;overflow:hidden;
 background:var(--bg);background-image:linear-gradient(180deg,#f6f5f0 0,var(--bg) 22rem);
 background-attachment:fixed;color:var(--ink);display:flex;flex-direction:column;
 font-variant-numeric:lining-nums tabular-nums;text-rendering:optimizeLegibility}
::selection{background:color-mix(in srgb,var(--brand-p3) 45%,white);color:var(--navy)}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:2px;text-decoration-thickness:1px}
b,strong{font-weight:600}
.mono{font-family:var(--mono);font-size:.86em;letter-spacing:-.01em}
/* One focus ring for the whole tool, and only for the keyboard. */
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:var(--radius-xs)}
*{scrollbar-width:thin;scrollbar-color:rgba(12,46,63,.22) transparent}
*::-webkit-scrollbar{width:9px;height:9px}
*::-webkit-scrollbar-thumb{background:rgba(12,46,63,.18);border-radius:99px;border:3px solid transparent;background-clip:padding-box}
*::-webkit-scrollbar-thumb:hover{background:rgba(12,46,63,.3);background-clip:padding-box}
*::-webkit-scrollbar-track{background:transparent}

/* ---------------------------------------------------------------- masthead */
.top{flex:none;background:linear-gradient(180deg,#123b50 0%,var(--navy) 62%);
 color:var(--brand-s5);position:relative;
 box-shadow:0 1px 0 rgba(12,46,63,.16),0 6px 18px -12px rgba(12,46,63,.5)}
/* The gold is a hairline, not a band: the guidelines allow it sparingly, and at one
   pixel it reads as a rule ruled under a masthead rather than as decoration. */
.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
 background:linear-gradient(90deg,var(--gold) 0%,color-mix(in srgb,var(--gold) 45%,transparent) 62%,transparent 100%)}
.top-in{padding:0 var(--s6);height:3.5rem;display:flex;align-items:center;gap:var(--s5);
 max-width:1900px;margin:0 auto;width:100%}
.brand{display:flex;align-items:baseline;gap:.6rem;margin-right:var(--s4);
 padding-right:var(--s4);border-right:1px solid rgba(255,255,255,.12)}
.brand b{font:400 1.22rem/1 var(--serif);letter-spacing:-.005em;color:#fff}
.brand span{font-size:.64rem;color:color-mix(in srgb,var(--brand-p3) 80%,white);
 letter-spacing:.22em;text-transform:uppercase;font-weight:600}
.nav{display:flex;gap:.1rem;align-self:stretch}
.nav a{display:flex;align-items:center;gap:.45rem;padding:0 .85rem;position:relative;
 color:color-mix(in srgb,var(--brand-s5) 72%,var(--brand-p3));
 font-size:.92rem;letter-spacing:.005em;transition:color .15s var(--ease)}
.nav a::after{content:"";position:absolute;left:.85rem;right:.85rem;bottom:0;height:2px;
 background:var(--gold);border-radius:2px 2px 0 0;opacity:0;transform:scaleX(.6);
 transform-origin:center;transition:opacity .18s var(--ease),transform .18s var(--ease)}
.nav a:hover{color:#fff;text-decoration:none}
.nav a[aria-current]{color:#fff}
.nav a[aria-current]::after{opacity:1;transform:scaleX(1)}
.top .right{margin-left:auto;display:flex;align-items:center;gap:var(--s4);
 font-size:var(--t-xs);color:color-mix(in srgb,var(--brand-p3) 88%,white);letter-spacing:.005em}
.top .right b{color:#fff;font-weight:600}
.top .pill{background:rgba(255,255,255,.06);color:var(--brand-s5);
 box-shadow:inset 0 0 0 1px rgba(137,178,196,.35)}
.top .pill.warn{color:color-mix(in srgb,var(--gold) 70%,white);background:rgba(193,155,43,.1);
 box-shadow:inset 0 0 0 1px rgba(193,155,43,.42)}

/* ---------------------------------------------------------------- page */
.wrap{flex:1;min-height:0;display:flex;flex-direction:column;gap:var(--s3);
 padding:var(--s4) var(--s6) var(--s5);max-width:1900px;margin:0 auto;width:100%}
.page-head{flex:none;display:flex;align-items:baseline;gap:var(--s4);flex-wrap:wrap;
 padding:0 .1rem .7rem;border-bottom:1px solid var(--line)}
.page-head h1{font:400 var(--t-display)/1.1 var(--serif);letter-spacing:-.018em;margin:0;
 color:var(--navy)}
.page-head p{margin:0;color:var(--ink-3);font-size:var(--t-sm);flex:1;min-width:22ch;
 max-width:86ch;line-height:1.5}
.page-head .tools{margin-left:auto;display:flex;align-items:center;gap:var(--s2)}

/* The board: a grid that fills the rest of the screen. Each page names its areas. */
.board{flex:1;min-height:0;display:grid;gap:var(--s3)}
.board>.card{margin:0;min-height:0}

/* Legacy flow layout, kept for anything rendered outside a board. */
.cols{display:grid;gap:var(--s3);align-items:start}
.cols.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.cols.side{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}

/* ---------------------------------------------------------------- card */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
 box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0;overflow:hidden}
.card>header{flex:none;padding:var(--s4) var(--s5) .6rem}
.card h2{font:400 1.16rem/1.25 var(--serif);margin:0;color:var(--navy);letter-spacing:-.012em}
.card h2 small{font:400 var(--t-xs) var(--sans);color:var(--ink-3);margin-left:.5rem;letter-spacing:0}
.card h2 .of{font:600 var(--t-label)/1 var(--sans);letter-spacing:.1em;color:var(--ink-3);
 margin-left:.55rem;vertical-align:.12em;font-variant-numeric:tabular-nums}
.card .why{margin:.25rem 0 0;font-size:var(--t-xs);color:var(--ink-3);line-height:1.5;max-width:74ch}
.card .body{flex:1;min-height:0;overflow:auto;padding:var(--s2) var(--s5) var(--s4);
 scrollbar-gutter:stable;
 /* Two pairs: the white ones scroll with the content and cover the shadows when there is
    nothing past the edge; the shadows are fixed to the panel. So an edge with more behind
    it is shaded, and an edge with nothing behind it is clean - the browser's own answer to
    "is this cut off", with nothing for a script to keep in step with. */
 background:
  linear-gradient(var(--surface) 34%,rgba(255,255,255,0)) top/100% 1.6rem no-repeat local,
  linear-gradient(rgba(255,255,255,0),var(--surface) 66%) bottom/100% 1.6rem no-repeat local,
  radial-gradient(farthest-side at 50% 0,rgba(12,46,63,.13),rgba(12,46,63,0)) top/100% .55rem no-repeat scroll,
  radial-gradient(farthest-side at 50% 100%,rgba(12,46,63,.13),rgba(12,46,63,0)) bottom/100% .55rem no-repeat scroll}
.card .foot{flex:none;padding:var(--s3) var(--s5);border-top:1px solid var(--line-soft);
 background:var(--surface-2);display:flex;gap:var(--s2);align-items:center;flex-wrap:wrap}

/* ---------------------------------------------------------------- metric */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:1px;
 background:var(--line);border:1px solid var(--line);border-radius:var(--radius);
 overflow:hidden;box-shadow:var(--shadow)}
.metric{background:var(--surface);padding:var(--s3) var(--s4) var(--s4);
 transition:background .2s var(--ease)}
.metric:hover{background:var(--surface-2)}
.metric .k{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);display:block;margin-bottom:.45rem;font-weight:600}
.metric .v{font-size:2rem;font-weight:600;letter-spacing:-.03em;line-height:1;
 display:block;color:var(--navy);font-variant-numeric:lining-nums tabular-nums}
.metric .v small{font-size:.9rem;font-weight:500;color:var(--ink-3);letter-spacing:0;margin-left:.15rem}
.metric .c{display:block;margin-top:.45rem;font-size:var(--t-xs);color:var(--ink-3);line-height:1.45}
.metric.good .v{color:var(--good)}.metric.warn .v{color:var(--warn)}.metric.bad .v{color:var(--bad)}

/* ---------------------------------------------------------------- rows */
.rows{display:flex;flex-direction:column}
.r{display:flex;align-items:center;gap:var(--s3);padding:.55rem 0;
 border-bottom:1px solid var(--line-soft)}
.r:last-child{border-bottom:0}
.r .lbl{flex:1;min-width:0;color:var(--ink-2);font-size:var(--t-sm)}
.r .lbl b{color:var(--navy);font-weight:600;font-size:var(--t-body)}
.r .val{font-weight:600;white-space:nowrap;color:var(--navy);font-variant-numeric:tabular-nums}
/* A column of figures is read down, so it is set to one width and aligned on the right.
   Ragged numbers are the difference between a table and a list of facts. */
.r .num{flex:none;width:4.5rem;text-align:right;font-variant-numeric:tabular-nums;
 color:var(--ink-2);font-size:var(--t-sm)}
.r.head .num{color:var(--ink-3);font-size:var(--t-label);letter-spacing:.14em;
 text-transform:uppercase;font-weight:600}
.of-n{color:var(--ink-3);font-weight:400;font-size:var(--t-xs);margin-left:.35rem;
 font-variant-numeric:tabular-nums}
.r .sub{color:var(--ink-3);font-size:var(--t-xs);white-space:nowrap}
.r .sub.mono{font-size:.74rem;letter-spacing:0;color:var(--ink-4)}
.r .d{display:block;color:var(--ink-3);font-size:var(--t-xs);margin-top:.15rem;
 white-space:normal;line-height:1.45}
.r.head{padding-bottom:.4rem;border-bottom:1px solid var(--line)}
.r.head span{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);font-weight:600}
.r.link,.r.pick{cursor:pointer;border-radius:var(--radius-sm);
 padding-left:.6rem;padding-right:.6rem;margin:0 -.6rem;
 transition:background .16s var(--ease),box-shadow .16s var(--ease)}
.r.link:hover,.r.pick:hover{background:var(--surface-2)}
.r.link.on,.r.pick.on{background:var(--accent-soft);box-shadow:inset 2px 0 0 var(--accent)}

/* An engagement is a name, a state, and five things you can do to it. The first two own
   the first line; the rest sit under them, so a client with a long name is not the thing
   that has to give way. */
.r.engagement{flex-wrap:wrap;align-items:flex-start;padding:.7rem 0 .6rem;row-gap:.35rem}
.r.engagement .lbl{flex:1 1 14rem}
.r.engagement>.pill{margin-top:.15rem}
.r.engagement .acts{flex:1 0 100%;display:flex;flex-wrap:wrap;gap:.25rem;justify-content:flex-end;
 align-items:center}
.r.engagement .acts button.quiet{padding:.3rem .5rem;font-size:var(--t-xs);color:var(--ink-3)}
.r.engagement .acts button.quiet:hover{color:var(--navy)}

/* ---------------------------------------------------------------- pill */
/* Quiet by design: a wash, a hairline and a dot carrying the colour. A row of saturated
   badges is the thing that makes a dashboard look like a toy. */
.pill{display:inline-flex;align-items:center;gap:.4rem;padding:.16rem .55rem;border-radius:99px;
 font-size:var(--t-xs);font-weight:600;letter-spacing:.005em;white-space:nowrap;
 background:var(--surface-2);color:var(--ink-2);box-shadow:inset 0 0 0 1px var(--line)}
.pill.good{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px var(--good-line)}
.pill.warn{background:var(--warn-soft);color:var(--warn);box-shadow:inset 0 0 0 1px var(--warn-line)}
.pill.bad{background:var(--bad-soft);color:var(--bad);box-shadow:inset 0 0 0 1px var(--bad-line)}
.pill.accent{background:var(--accent-soft);color:var(--accent-ink);box-shadow:inset 0 0 0 1px var(--accent-line)}
.dot{width:.38rem;height:.38rem;border-radius:99px;background:currentColor;flex:none;
 box-shadow:0 0 0 2px color-mix(in srgb,currentColor 18%,transparent)}

/* ---------------------------------------------------------------- bar */
.bar{height:.3rem;border-radius:99px;background:var(--surface-sunken);overflow:hidden;
 box-shadow:inset 0 0 0 1px var(--line-soft)}
.bar>i{display:block;height:100%;background:var(--accent);border-radius:99px;
 transition:width .5s var(--ease)}
.bar.good>i{background:var(--good)}.bar.warn>i{background:var(--gold)}
.bar.bad>i{background:var(--bad)}

/* ---------------------------------------------------------------- controls */
button,.btn{font:600 var(--t-sm)/1 var(--sans);background:var(--surface);color:var(--navy);
 border:1px solid var(--line-strong);border-radius:var(--radius-sm);
 padding:.5rem .85rem;cursor:pointer;letter-spacing:.005em;
 box-shadow:0 1px 1px rgba(12,46,63,.04);
 transition:background .16s var(--ease),border-color .16s var(--ease),
  box-shadow .16s var(--ease),transform .12s var(--ease)}
button:hover,.btn:hover{background:var(--surface-2);border-color:var(--accent);
 box-shadow:0 1px 2px rgba(12,46,63,.08)}
button:active{transform:translateY(1px);box-shadow:none}
button.primary{background:linear-gradient(180deg,#17465f,var(--navy));color:#fff;
 border-color:var(--navy);box-shadow:0 1px 2px rgba(12,46,63,.24)}
button.primary:hover{background:linear-gradient(180deg,#1b5271,#103a4f);border-color:var(--navy);
 box-shadow:0 2px 6px -1px rgba(12,46,63,.3)}
button.quiet{background:transparent;border-color:transparent;color:var(--accent-ink);
 padding:.4rem .55rem;box-shadow:none}
button.quiet:hover{color:var(--navy);background:var(--accent-soft);border-color:transparent}
button.ghost{background:transparent;color:var(--ink-2);box-shadow:none}
button.ghost:hover{background:var(--surface-2);color:var(--navy)}
button.small{padding:.32rem .6rem;font-size:var(--t-xs)}
button:disabled{opacity:.42;cursor:not-allowed;box-shadow:none}
button:disabled:hover{background:var(--surface);border-color:var(--line-strong)}
input,textarea,select{font:var(--t-body) var(--sans);background:var(--surface);color:var(--ink);
 border:1px solid var(--line-strong);border-radius:var(--radius-sm);padding:.5rem .65rem;width:100%;
 margin:0 0 .6rem;outline:none;box-shadow:inset 0 1px 2px rgba(12,46,63,.04);
 transition:border-color .16s var(--ease),box-shadow .16s var(--ease)}
input:focus,textarea:focus,select:focus{border-color:var(--accent);
 box-shadow:0 0 0 3px var(--accent-soft),inset 0 1px 2px rgba(12,46,63,.04)}
input::placeholder{color:var(--ink-4)}
label{display:block;font-size:var(--t-label);color:var(--ink-3);margin:0 0 .3rem;
 letter-spacing:.12em;text-transform:uppercase;font-weight:600}
select{width:auto;padding:.35rem .55rem;margin:0}

/* ---------------------------------------------------------------- states */
.card .body:has(>.empty:only-child){display:flex;align-items:center;justify-content:center}
.empty{padding:var(--s6) var(--s4);text-align:center;color:var(--ink-3);font-size:var(--t-xs);
 line-height:1.55;max-width:44ch;margin:0 auto}
.empty b{display:block;color:var(--navy);font:400 var(--t-subtitle)/1.3 var(--serif);
 margin-bottom:.35rem;letter-spacing:-.005em}
.note{font-size:var(--t-xs);color:var(--ink-3);margin-top:var(--s3);line-height:1.5}
.skel{height:.7rem;border-radius:3px;background:linear-gradient(90deg,var(--surface-2),var(--surface-sunken),var(--surface-2));
 background-size:200% 100%;animation:sh 1.4s ease-in-out infinite;margin:.6rem 0}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){
 *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;
  transition-duration:.001ms!important}
}

/* --------------------------------------------------- narrower than a desk */
/* One screen, no scrolling, is the rule at desk width. Below it the same rule hides
   whatever does not fit, with no way to reach it: so the board becomes one column, the
   cards take their own height, and the page scrolls like a page. */
@media (max-width:1100px){
 html,body{overflow:auto}
 .wrap{overflow:visible}
 .board{display:block!important}
 .board>.card{margin-bottom:var(--s3)}
 .card .body{max-height:none}
 .chrome{flex-wrap:wrap;gap:.3rem .8rem}
 .page-head{flex-direction:column;align-items:flex-start;gap:.2rem}
}
@media (max-width:640px){
 .wrap{padding-left:16px;padding-right:16px}
 .top-in{padding-left:16px;padding-right:16px}
 .r{flex-wrap:wrap;gap:.3rem}
 .modal .card{width:auto;max-width:none;margin:0 .6rem}
}

/* ------------------------------------------------------------- offline */
#offline{display:none;margin:0 0 var(--s3);padding:.6rem .9rem;border-radius:var(--radius-sm);
 border:1px solid var(--bad-line);background:var(--bad-soft);
 color:var(--navy);font-size:var(--t-sm);box-shadow:var(--shadow)}
#offline.on{display:block}
#offline .code{margin-left:.4rem;font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3)}

/* ---------------------------------------------------------------- toast */
#toast{position:fixed;left:50%;bottom:1.8rem;transform:translate(-50%,16px);z-index:60;
 max-width:min(680px,92vw);padding:.75rem 1.15rem;border-radius:var(--radius-sm);
 background:var(--navy);border-top:2px solid var(--gold);color:var(--brand-s5);font-size:var(--t-sm);
 box-shadow:var(--shadow-modal);opacity:0;pointer-events:none;
 transition:opacity .2s var(--ease),transform .2s var(--ease)}
#toast.on{opacity:1;transform:translate(-50%,0)}
#toast.bad{border-top-color:color-mix(in srgb,var(--brand-s2) 60%,var(--brand-p3));
 background:color-mix(in srgb,var(--brand-s2) 78%,var(--navy))}
#toast.good{border-top-color:var(--brand-p4)}
#toast .code{font-family:var(--mono);font-size:var(--t-xs);color:var(--brand-p3);display:block;margin-top:.25rem}

/* ---------------------------------------------------------------- modal */
.modal{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;
 background:color-mix(in srgb,var(--navy) 38%,transparent);padding:var(--s7);
 backdrop-filter:blur(2px);animation:fade .18s var(--ease)}
@keyframes fade{from{opacity:0}to{opacity:1}}
.modal>.card{width:min(56rem,100%);max-height:100%;box-shadow:var(--shadow-modal);
 animation:rise .22s var(--ease)}
.modal>.card>header{padding:var(--s5) var(--s6) .7rem}
.modal>.card h2{font-size:1.32rem;line-height:1.25}
.modal>.card .body{padding:var(--s2) var(--s6) var(--s4)}
.modal>.card .foot{padding:var(--s3) var(--s6)}
@keyframes rise{from{opacity:0;transform:translateY(8px) scale(.995)}to{opacity:1;transform:none}}
.modal>.card.narrow{width:min(34rem,100%)}
.modal .foot{display:flex;gap:var(--s2);align-items:center;justify-content:flex-end}
.modal .foot .spacer{margin-right:auto;font-size:var(--t-xs);color:var(--ink-3)}
.field{margin:0 0 var(--s3)}
.field .hint{font-size:var(--t-xs);color:var(--ink-3);margin:-.2rem 0 .4rem;line-height:1.45}
.field select{width:100%;padding:.5rem .65rem}

/* ---------------------------------------------------------------- review panel */
.excerpt{font-family:var(--mono);font-size:var(--t-sm);line-height:1.6;white-space:pre-wrap;
 background:var(--surface-sunken);border-radius:0 var(--radius-sm) var(--radius-sm) 0;padding:.75rem .9rem;
 margin:.25rem 0 var(--s3);box-shadow:inset 3px 0 0 var(--accent);color:var(--ink);
 max-height:14rem;overflow:auto}
.kv{display:grid;grid-template-columns:minmax(7rem,auto) 1fr;gap:.5rem var(--s4);
 font-size:var(--t-sm);margin:.25rem 0 var(--s3);align-items:baseline}
.kv dt{color:var(--ink-3);font-size:var(--t-label);letter-spacing:.1em;text-transform:uppercase;
 font-weight:600;white-space:nowrap}
.kv dd{margin:0;color:var(--ink);word-break:break-word;font-size:var(--t-body);
 font-variant-numeric:lining-nums tabular-nums}
.kv dd .sub{color:var(--ink-3);font-size:var(--t-xs);font-weight:400}
.kv dd input{margin:0}
.section-label{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);margin:var(--s4) 0 .4rem;font-weight:600;
 display:flex;align-items:center;gap:var(--s2)}
.section-label::after{content:"";flex:1;height:1px;background:var(--line-soft)}
.reveal{display:flex;align-items:center;gap:var(--s3);padding:.8rem .9rem;border-radius:var(--radius-sm);
 background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line);margin:.25rem 0 var(--s3)}
.reveal p{margin:0;font-size:var(--t-sm);color:var(--ink-2);flex:1;line-height:1.5}
.reveal button{background:linear-gradient(180deg,#17465f,var(--navy));color:#fff;
 border-color:var(--navy);box-shadow:0 1px 2px rgba(12,46,63,.24);white-space:nowrap}
.reveal button:hover{background:linear-gradient(180deg,#1b5271,#103a4f);border-color:var(--navy)}
.decide{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:.35rem}
.decide button.on{background:linear-gradient(180deg,#17465f,var(--navy));color:#fff;border-color:var(--navy)}

/* ---------------------------------------------------------------- lists that are work */
.r .why-line{display:block;font-size:var(--t-xs);color:var(--ink-3);margin-top:.2rem;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:34rem}
.count{display:inline-grid;place-items:center;min-width:1.4rem;height:1.4rem;padding:0 .4rem;
 border-radius:99px;font-size:var(--t-xs);font-weight:700;background:var(--gold);color:var(--navy);
 box-shadow:0 1px 2px rgba(12,46,63,.16)}
.attention{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;font-size:var(--t-xs)}
.attention b{color:var(--navy)}
.toggle{display:inline-flex;align-items:center;gap:.4rem;font-size:var(--t-xs);color:var(--ink-3);
 cursor:pointer;user-select:none;text-transform:none;letter-spacing:0;margin:0;font-weight:400}
.toggle input{width:auto;margin:0}

/* ---------------------------------------------------------------- steps */
.steps{display:flex;flex-direction:column;gap:.15rem}
.step{display:flex;gap:var(--s3);align-items:flex-start;padding:.55rem .6rem;
 border-radius:var(--radius-sm);transition:background .16s var(--ease)}
.step.now{background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line)}
.step .mark{width:1.4rem;height:1.4rem;border-radius:99px;flex:none;margin-top:.05rem;
 display:grid;place-items:center;font-size:var(--t-xs);font-weight:600;
 background:var(--surface-2);color:var(--ink-3);box-shadow:inset 0 0 0 1px var(--line)}
.step.done .mark{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px var(--good-line)}
.step.now .mark{background:var(--navy);color:#fff;box-shadow:none}
.step>span:not(.mark):not(.go){flex:1;min-width:0}
.step .t{display:block;font-size:var(--t-sm);color:var(--navy);font-weight:600}
.step.done .t{color:var(--ink-3);font-weight:500}
.step .d{display:block;font-size:var(--t-xs);color:var(--ink-3);margin-top:.1rem;line-height:1.5}
.step .go{margin-left:auto}

/* ---------------------------------------------------------------- node map */
.map-groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));
 gap:var(--s4) var(--s5)}
.map-group>h3{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);margin:0 0 .45rem;font-weight:600;
 padding-bottom:.35rem;border-bottom:1px solid var(--line-soft)}
.map-group{break-inside:avoid}
.map{display:flex;flex-wrap:wrap;gap:.15rem .45rem}
.node{display:inline-flex;align-items:center;gap:.35rem;padding:.12rem .3rem;
 border-radius:var(--radius-xs);font-size:var(--t-xs);line-height:1.4;
 background:transparent;color:var(--ink-4);box-shadow:none;
 cursor:default;transition:background .16s var(--ease),color .16s var(--ease)}
.node .id{font-family:var(--mono);font-size:.74rem}
.node[title]{cursor:help}
.node.used{color:var(--ink-2);background:var(--surface-2);box-shadow:inset 0 0 0 1px var(--line-soft);
 padding:.12rem .4rem}
.node.passed{padding:.12rem .4rem;color:var(--good);background:var(--good-soft);box-shadow:inset 0 0 0 1px var(--good-line)}
.node.failed{padding:.12rem .4rem;color:var(--bad);background:var(--bad-soft);box-shadow:inset 0 0 0 1px var(--bad-line);font-weight:600}
.node.active{padding:.12rem .4rem;color:var(--accent-ink);background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line)}
.node .ring{width:.55rem;height:.55rem;border-radius:99px;flex:none;
 border:1.5px solid currentColor;border-top-color:transparent;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.legend{display:flex;gap:var(--s4);flex-wrap:wrap;margin:0 0 var(--s3);padding-bottom:var(--s2);
 font-size:var(--t-xs);color:var(--ink-3);border-bottom:1px solid var(--line-soft)}
.legend span{display:inline-flex;align-items:center;gap:.4rem}
.legend i{width:.55rem;height:.55rem;border-radius:2px;display:inline-block;
 box-shadow:inset 0 0 0 1px rgba(12,46,63,.12)}
.diag{margin-top:var(--s3)}
.diag .d-row{padding:.55rem .85rem;border-radius:0 var(--radius-sm) var(--radius-sm) 0;
 background:var(--surface-2);box-shadow:inset 3px 0 0 var(--bad);margin-bottom:.45rem}
.diag .d-row .code{font-family:var(--mono);font-size:var(--t-xs);color:var(--bad);font-weight:600}
.diag .d-row .msg{display:block;margin-top:.2rem;color:var(--ink-2);font-size:var(--t-sm);line-height:1.5}

details>summary{cursor:pointer;color:var(--ink-3);font-size:var(--t-sm);list-style:none;
 padding:.3rem 0;user-select:none;transition:color .16s var(--ease)}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"\203A";display:inline-block;margin-right:.5rem;
 transition:transform .18s var(--ease);color:var(--ink-4)}
details[open]>summary::before{transform:rotate(90deg)}
details>summary:hover{color:var(--navy)}
"""

SHELL = """<script>
// The three things every page does: escape, format, and say what happened.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"'`]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;','`':'&#96;'}[c]));
const pct = v => (v === null || v === undefined)
  ? '<span style="color:var(--ink-4)">not yet</span>' : (v * 100).toFixed(1) + '%';
const num = (v, dash = 'not yet') => (v === null || v === undefined)
  ? '<span style="color:var(--ink-4)">' + dash + '</span>' : esc(v);
const plural = (n, one, many) => n + ' ' + (n === 1 ? one : many);
/* `data-` attributes from an object, escaped: how a value reaches a handler. */
const data = o => Object.entries(o || {}).map(([k, v]) => ` data-${k}="${esc(v)}"`).join('');

/* What a row or a button does, by name. A row carries `data-act` and its values in
   other data attributes; nothing interpolates a value into script, so a client's
   apostrophe cannot close anything and a client's file cannot open anything.

   One listener on the document, so rows redrawn on the next poll keep working without
   being rebound - and the same listener answers Enter and Space, which is how anybody
   working from the keyboard reaches a row at all. */
const ACTIONS = {};
function _fire(ev) {
  const el = ev.target.closest('[data-act]');
  if (!el || !ACTIONS[el.dataset.act]) return;
  if (ev.type === 'keydown') {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    if (ev.target.closest('input,textarea,select')) return;
  }
  ev.preventDefault();
  ev.stopPropagation();
  ACTIONS[el.dataset.act](el.dataset, el, ev);
}
document.addEventListener('click', _fire);
document.addEventListener('keydown', _fire);

/* The server, when a page cannot reach it. Said once and left standing - not toasted every
   few seconds - and taken down as soon as a load succeeds. The page keeps whatever it had:
   stale numbers with a date on them beat an empty page that reads as "nothing to do". */
let OFFLINE_SINCE = null;
function offline(err) {
  if (OFFLINE_SINCE === null) OFFLINE_SINCE = new Date();
  const bar = $('offline');
  if (!bar) return;
  const when = OFFLINE_SINCE.toTimeString().slice(0, 5);
  bar.className = 'on';
  bar.setAttribute('role', 'alert');
  bar.innerHTML = `<b>This page cannot reach the server</b> &mdash; nothing below has changed
    since ${esc(when)}. Runs carry on without it; this page only reads.
    ${err && err.code ? `<span class="code">${esc(err.code)}</span>` : ''}`;
}
function online() {
  OFFLINE_SINCE = null;
  const bar = $('offline');
  if (bar) { bar.className = ''; bar.innerHTML = ''; }
}

let toastTimer = null;
function say(message, kind, code) {
  const box = $('toast');
  if (!box) return;
  box.className = kind || '';
  // A refusal is the one signal that a form was rejected; announced, not only shown.
  box.setAttribute('role', kind === 'bad' ? 'alert' : 'status');
  box.setAttribute('aria-live', kind === 'bad' ? 'assertive' : 'polite');
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
// When something happened, in the words a person uses: "4 min ago", "yesterday".
function ago(ts) {
  if (!ts) return '';
  const t = Date.parse(ts);
  if (isNaN(t)) return '';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.round(s / 60) + ' min ago';
  if (s < 86400) return Math.round(s / 3600) + ' h ago';
  if (s < 172800) return 'yesterday';
  return Math.round(s / 86400) + ' days ago';
}
const usd = v => (v === null || v === undefined) ? '' : '$' + Number(v).toFixed(2);

// A question asked in the page rather than in a browser pop-up: it can explain itself, it
// can require a reason, and it does not block everything else on the screen. Resolves to
// the answers by field name, or null if the person cancelled.
/* Open a dialog: at most one, with the focus moved into it and given back afterwards.

   Each modal used to add its own keydown listener to the document and some of its close
   paths bypassed the cleanup, so cancelling a dialog ten times left ten dead listeners, each
   holding a detached page. This is the one place any of that is written. */
function openModal(box) {
  document.querySelectorAll('.modal').forEach(m => m.remove());
  const came_from = document.activeElement;
  const onKey = e => { if (e.key === 'Escape') shut(); };
  const shut = () => {
    document.removeEventListener('keydown', onKey);
    box.dispatchEvent(new CustomEvent('modal-closed'));
    box.remove();
    if (came_from && came_from.focus) came_from.focus();
  };
  document.addEventListener('keydown', onKey);
  document.body.appendChild(box);
  const first = box.querySelector('input,textarea,select,button');
  if (first) first.focus();
  return shut;
}

function ask({title, why = '', body = '', fields = [], ok = 'Continue', danger = false, note = ''}) {
  return new Promise(resolve => {
    const box = document.createElement('div');
    box.className = 'modal';
    box.innerHTML = `<section class="card${body ? '' : ' narrow'}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <header><h2>${esc(title)}</h2>${why ? `<p class="why">${esc(why)}</p>` : ''}</header>
      <div class="body">${body ? `<div class="excerpt" style="max-height:min(22rem,45vh);font-family:var(--sans);font-size:.9rem">${esc(body)}</div>` : ''}${fields.map((f, n) => `<div class="field">
        <label for="ask_${n}">${esc(f.label)}${f.required ? '' : ' <span style="text-transform:none;letter-spacing:0">(optional)</span>'}</label>
        ${f.hint ? `<p class="hint">${esc(f.hint)}</p>` : ''}
        ${f.kind === 'select'
          ? `<select id="ask_${n}">${(f.options || []).map(o => `<option value="${esc(o.value)}"${o.value === f.value ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`
          : f.kind === 'textarea'
            ? `<textarea id="ask_${n}" rows="3" placeholder="${esc(f.placeholder || '')}">${esc(f.value || '')}</textarea>`
            : `<input id="ask_${n}" value="${esc(f.value || '')}" placeholder="${esc(f.placeholder || '')}">`}
      </div>`).join('')}${note ? `<p class="note" style="margin-top:0">${esc(note)}</p>` : ''}</div>
      <div class="foot"><button class="quiet" data-act="cancel">Cancel</button>
       <button class="primary" data-act="ok"${danger ? ' style="background:var(--bad);border-color:var(--bad)"' : ''}>${esc(ok)}</button></div>
    </section>`;
    // Inside this dialog, never by document id: two dialogs carry the same field ids, and
    // getElementById answers with whichever came first in the document - which is how the
    // visible dialog ends up reading the hidden one's fields.
    const field = n => box.querySelector('#ask_' + n);
    let shut = null;
    const finish = value => { if (shut) shut(); resolve(value); };
    const submit = () => {
      const out = {};
      for (let n = 0; n < fields.length; n++) {
        const v = field(n).value;
        if (fields[n].required && !String(v).trim()) {
          field(n).focus();
          return say(fields[n].label + ' is needed - it is recorded with the change.', 'bad');
        }
        out[fields[n].name] = v;
      }
      finish(out);
    };
    box.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit();
    });
    box.addEventListener('click', e => {
      if (e.target === box) finish(null);
      const act = e.target.dataset && e.target.dataset.act;
      if (act === 'cancel') finish(null);
      if (act === 'ok') submit();
    });
    shut = openModal(box);
    // Escape closes through openModal, which cannot know this dialog answers a promise.
    box.addEventListener('modal-closed', () => resolve(null));
    const first = box.querySelector('input,textarea,select,button.primary');
    if (first) first.focus();
  });
}

/* Poll something, politely: never twice at once, never while the tab is hidden, and more
   slowly each time the server does not answer - up to half a minute, back to normal the
   moment it does. A tab left open all day used to make about fifty thousand requests, and
   a dead server was asked at full rate for as long as the page was open. */
function poll(fn, ms) {
  let failures = 0, running = false, timer = null;
  const tick = async () => {
    if (running) return;
    if (document.hidden) return arm(ms);
    running = true;
    try { await fn(); failures = 0; }
    catch (e) { failures++; }
    finally { running = false; }
    arm(Math.min(ms * Math.pow(2, Math.min(failures, 3)), Math.max(ms, 30000)));
  };
  const arm = delay => { clearTimeout(timer); timer = setTimeout(tick, delay); };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  arm(ms);
  return tick;
}

// What is waiting on a person, on every page: a count on the Activity tab, and in the
// browser tab's title so it shows when the console is in the background.
const BASE_TITLE = document.title;
async function waiting() {
  let n = 0;
  try { n = (await get('/api/review')).length; } catch (e) { return; }
  const tab = document.querySelector('.nav a[href="/"]');
  if (tab) {
    let badge = tab.querySelector('.count');
    if (n && !badge) { badge = document.createElement('span'); badge.className = 'count'; badge.style.marginLeft = '.4rem'; tab.appendChild(badge); }
    if (badge) { if (n) { badge.textContent = n; badge.title = n + ' waiting on a person'; } else badge.remove(); }
  }
  document.title = (n ? '(' + n + ') ' : '') + BASE_TITLE;
}
waiting();
poll(waiting, 20000);

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
        ("/help", "Help"),
    )
    links = "".join(
        f'<a href="{path}"{" aria-current=\'page\'" if path == current else ""}>{label}</a>'
        for path, label in tabs
    )
    icon = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Crect width='32' height='32' rx='6' fill='%230c2e3f'/%3E"
        "%3Cpath d='M9 23l7-14 7 14' stroke='%23c19b2b' stroke-width='3' fill='none' "
        "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
    )
    return (
        f'<link rel="icon" href="{icon}">'
        f'<header class="top"><div class="top-in">'
        f'<span class="brand"><b>Automated Analyst</b><span>Chartwell</span></span>'
        f'<nav class="nav">{links}</nav>'
        f'<span class="right" id="chrome-right"></span>'
        f"</div></header>"
    )
