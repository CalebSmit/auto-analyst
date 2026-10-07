# ruff: noqa: E501 - this module is a stylesheet held in a string. Wrapping CSS to a
# hundred columns makes it harder to read, not easier.
"""The design language: Chartwell's colours and type, one screen per page, one set of parts.

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
thing that makes a tool look like a toy - and one row carries one pill, because three of
them is the same mistake made three times.

**A sequence is drawn as a sequence.** Steps are joined by a rail, which is the whole
difference between "here are seven tasks" and "here is where you are in one"; the rail
carries the colour of the part already done, so it measures rather than decorates. The step
somebody is on is the subject of the panel and a finished one costs a single line, because
the alternative puts most of the ink on the part nobody has to read again. Three pages wear
this and only one of them ever marks a step done - so nothing in it may depend on that.

**A component lives here or it does not exist.** The sheet is where a value is decided; a
page decides only which panel goes where. That rule was not free - P81 found nine things a
page had styled by hand, two of them in pixels on a page whose root is fluid, so they got
*proportionally smaller* on a bigger monitor. Anything with a general name and a value
chosen by eye is a local fix waiting to be reached for generally.
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
    instead of beside it, which is most of why a rule reads as drawn and not as left over.
    The first two separate content and are decoration, which is why they may be this faint.
    `--line-strong` is not decoration: it is the edge of a control, and on a white panel a
    white button has nothing else to say it is one. So it is measured the way the ink is,
    against the 3:1 a non-text indicator needs rather than the 4.5:1 a word does, and it
    clears it on all four surfaces - 3.13 on white, 3.06, 3.02 and 3.03 on the others. At
    .22 it was 1.54 and the control with the most consequence in a row, the one that
    changes state, was the one marked only by a line nobody could see. */
 --line:rgba(12,46,63,.14);
 --line-soft:rgba(12,46,63,.08);
 --line-strong:rgba(12,46,63,.51);

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
 /* Three layers each: a contact shadow, a near one, and a wide soft one that fades before
    it reaches the next panel. Two layers read as a sticker; the third is what makes a
    panel sit on the paper rather than on top of it (P170). */
 --shadow:0 1px 1px rgba(12,46,63,.04),0 2px 6px -2px rgba(12,46,63,.07),0 14px 30px -22px rgba(12,46,63,.14);
 --shadow-lift:0 1px 1px rgba(12,46,63,.05),0 6px 16px -6px rgba(12,46,63,.14),0 22px 44px -28px rgba(12,46,63,.18);
 --shadow-modal:0 24px 64px -12px rgba(12,46,63,.32),0 2px 8px rgba(12,46,63,.12);
 --ease:cubic-bezier(.32,.72,0,1);
}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
 /* Fluid: the whole board fits a 13-inch laptop and a 27-inch monitor alike. */
 font-size:clamp(12px,.55vw + 5.5px,14.5px);min-height:100%}
/* Lit paper. Two soft lights in the brand's own colours - Mint Mist from the top left,
   gold from the top right - over the paper gradient. Fixed to the window so they stay
   where the light would be while the page scrolls under them (P171). */
body{font:var(--t-body)/1.5 var(--sans);margin:0;min-height:100%;
 background:var(--bg);background-image:
  radial-gradient(60rem 28rem at 6% -12%,color-mix(in srgb,var(--brand-p4) 72%,transparent),transparent 70%),
  radial-gradient(46rem 22rem at 98% -10%,color-mix(in srgb,var(--gold) 22%,transparent),transparent 70%),
  linear-gradient(180deg,#f6f5f0 0,var(--bg) 22rem);
 background-attachment:fixed;color:var(--ink);display:flex;flex-direction:column;
 font-variant-numeric:lining-nums tabular-nums;text-rendering:optimizeLegibility}
::selection{background:color-mix(in srgb,var(--brand-p3) 45%,white);color:var(--navy)}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:2px;text-decoration-thickness:1px}
b,strong{font-weight:600}
.mono{font-family:var(--mono);font-size:.86em;letter-spacing:-.01em}
/* One focus ring for the whole tool, and only for the keyboard. It is named rather than
   written in, because the ground it lands on is not all one colour: the accent measures
   4.33 to 4.94 on the four papers and 2.40 on the chrome, and the chrome is where a
   keyboard arrives first. A dark surface redefines `--ring` for itself in one line. */
:root{--ring:var(--accent)}
:focus-visible{outline:2px solid var(--ring);outline-offset:2px;border-radius:var(--radius-xs)}
*{scrollbar-width:thin;scrollbar-color:rgba(12,46,63,.22) transparent}
*::-webkit-scrollbar{width:9px;height:9px}
*::-webkit-scrollbar-thumb{background:rgba(12,46,63,.18);border-radius:99px;border:3px solid transparent;background-clip:padding-box}
*::-webkit-scrollbar-thumb:hover{background:rgba(12,46,63,.3);background-clip:padding-box}
*::-webkit-scrollbar-track{background:transparent}

/* ---------------------------------------------------------------- masthead */
/* Sticky because it carries the two counts - what needs a person, and what is waiting
   on an answer - and the page scrolls now. A number you have to scroll back up to read
   is a number nobody reads. */
.top{flex:none;background:linear-gradient(180deg,#123b50 0%,var(--navy) 62%);
 --ring:var(--brand-p3);
 color:var(--brand-s5);position:sticky;top:0;z-index:30;overflow:hidden;
 box-shadow:0 1px 0 rgba(12,46,63,.16),0 6px 18px -12px rgba(12,46,63,.5)}
/* Three lights moving slowly under the chrome - Steel Blue, the pale blue, a breath of
   gold. It is the one place the tool is allowed to be beautiful for its own sake, because
   it is the one place that carries nothing a person has to read closely. Alternating and
   eighteen seconds long so it is noticed as life rather than watched as an animation; the
   reduced-motion rule below stops it. */
.top::before{content:"";position:absolute;inset:-60% -8%;pointer-events:none;z-index:0;
 background:
  radial-gradient(40rem 16rem at 16% 70%,color-mix(in srgb,var(--brand-p2) 82%,transparent),transparent 70%),
  radial-gradient(32rem 13rem at 64% 10%,color-mix(in srgb,var(--brand-p3) 50%,transparent),transparent 70%),
  radial-gradient(24rem 11rem at 94% 100%,color-mix(in srgb,var(--gold) 36%,transparent),transparent 70%);
 animation:aurora 18s var(--ease) infinite alternate}
@keyframes aurora{from{transform:translate3d(-3%,0,0) scale(1)}to{transform:translate3d(3%,-7%,0) scale(1.08)}}
.top-in{position:relative;z-index:1}
/* The gold is a hairline, not a band: the guidelines allow it sparingly, and at one
   pixel it reads as a rule ruled under a masthead rather than as decoration. */
.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;
 background:linear-gradient(90deg,var(--gold) 0%,color-mix(in srgb,var(--gold) 45%,transparent) 62%,transparent 100%)}
.top-in{padding:0 var(--s6);height:3.5rem;display:flex;align-items:center;gap:var(--s5);
 max-width:1900px;margin:0 auto;width:100%}
.brand{display:flex;align-items:baseline;gap:.6rem;margin-right:var(--s4);
 padding-right:var(--s4);border-right:1px solid rgba(255,255,255,.12)}
.brand b{font:400 1.3rem/1 var(--serif);letter-spacing:-.012em;color:#fff;
 text-shadow:0 1px 0 rgba(0,0,0,.18)}
.brand span{font-size:.64rem;color:color-mix(in srgb,var(--brand-p3) 80%,white);
 letter-spacing:.22em;text-transform:uppercase;font-weight:600}
.nav{display:flex;gap:.1rem;align-self:stretch}
.nav a{display:flex;align-items:center;gap:.45rem;padding:0 .85rem;position:relative;
 color:color-mix(in srgb,var(--brand-s5) 72%,var(--brand-p3));
 font-size:.92rem;letter-spacing:.005em;transition:color .15s var(--ease)}
.nav a::after{content:"";position:absolute;left:.85rem;right:.85rem;bottom:0;height:2px;
 background:var(--gold);border-radius:2px 2px 0 0;opacity:0;transform:scaleX(.6);
 transform-origin:center;transition:opacity .18s var(--ease),transform .18s var(--ease)}
.nav a:hover{color:#fff;text-decoration:none;background:rgba(255,255,255,.05)}
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
.wrap{flex:1;display:flex;flex-direction:column;gap:var(--s3);
 padding:var(--s4) var(--s6) var(--s5);max-width:1900px;margin:0 auto;width:100%}
.page-head{flex:none;display:flex;align-items:baseline;gap:var(--s4);flex-wrap:wrap;
 padding:0 .1rem .7rem;border-bottom:1px solid var(--line)}
.page-head h1{font:400 var(--t-display)/1.1 var(--serif);letter-spacing:-.018em;margin:0;
 color:var(--navy);background:linear-gradient(90deg,var(--navy),var(--brand-p2));
 -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
 padding-right:.1em}
.page-head p{margin:0;color:var(--ink-3);font-size:var(--t-sm);flex:1;min-width:22ch;
 max-width:86ch;line-height:1.5}
.page-head .tools{margin-left:auto;display:flex;align-items:center;gap:var(--s2)}

/* The board: a grid whose rows are as tall as what is in them. Each page names its areas.

   It used to fill the screen exactly, every row an equal share of whatever height there
   was. Measured across the three board pages at a desk viewport, that was wrong in both
   directions at once: seven of twenty panels hid content behind an inner scrollbar - Live
   activity showing a sixth of what it had, What is wired a quarter - while eight of twenty
   sat under seventy per cent full. A reader scrolled inside twelve boxes instead of
   scrolling one page, and a box only tells you it scrolls once you have found it.

   The rule the old one was keeping - everything at a glance, no scrolling - is kept where
   it can be: the chrome is sticky, so the counts that say what needs a person are in view
   wherever the page is. What could not be kept was the claim, because the board was not
   showing everything at a glance; it was hiding most of it. */
.board{display:grid;gap:var(--s3);align-content:start}
.board>.card{margin:0;min-height:0}

/* Legacy flow layout, kept for anything rendered outside a board. */
.cols{display:grid;gap:var(--s3);align-items:start}
.cols.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.cols.side{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr)}

/* ---------------------------------------------------------------- card */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
 box-shadow:var(--shadow);display:flex;flex-direction:column;min-height:0;overflow:hidden;
 position:relative;transition:box-shadow .3s var(--ease),border-color .3s var(--ease)}
/* The signature: a two-pixel rule along the top of every panel, Steel Blue fading out to
   the right. One mark, the same on every panel, is what makes a set of boxes read as one
   designed thing rather than as boxes. */
.card::before{content:"";position:absolute;left:0;right:0;top:0;height:2px;z-index:1;
 background:linear-gradient(90deg,var(--brand-p2),color-mix(in srgb,var(--brand-p3) 55%,transparent) 60%,transparent)}
.board>.card:hover{box-shadow:var(--shadow-lift);border-color:color-mix(in srgb,var(--accent) 35%,var(--line))}
/* The board arrives: each panel rises in a beat after the one before it. Half a second in
   all, once, on load - enough to feel the page assemble, not enough to wait for. */
.board>.card{animation:rise .55s var(--ease) both;animation-delay:calc(var(--i,0)*70ms)}
.board>.card:nth-child(2){--i:1}.board>.card:nth-child(3){--i:2}.board>.card:nth-child(4){--i:3}
.board>.card:nth-child(5){--i:4}.board>.card:nth-child(6){--i:5}.board>.card:nth-child(7){--i:6}
.board>.card:nth-child(8){--i:7}.board>.card:nth-child(n+9){--i:8}
.card>header{flex:none;padding:var(--s4) var(--s5) .6rem}
.card h2{font:400 1.24rem/1.25 var(--serif);margin:0;color:var(--navy);letter-spacing:-.016em}
.card h2 small{font:400 var(--t-xs) var(--sans);color:var(--ink-3);margin-left:.5rem;letter-spacing:0}
.card h2 .of{font:600 var(--t-label)/1 var(--sans);letter-spacing:.1em;color:var(--ink-3);
 margin-left:.55rem;vertical-align:.12em;font-variant-numeric:tabular-nums}
.card .why{margin:.25rem 0 0;font-size:var(--t-xs);color:var(--ink-3);line-height:1.5;max-width:74ch}
.card .body{flex:1;min-height:0;padding:var(--s2) var(--s5) var(--s4);}

/* A stream: a panel whose height is not this design's to decide.

   The test is **whose length it is**. A panel with one row per step of setup, per practice
   group, per recipe, per seam is as long as this build made it, and it is as tall as what
   it holds. A panel with one row per run, per engagement, per open question, per week of
   history is as long as the firm's own work, and nothing here can know how long that is -
   so it gets a cap and scrolls inside it.

   P142 wrote the first half of that and applied a different one. "Content that has no end"
   was the reason given; what actually got a cap was whatever looked long on a screen with
   three runs on it. So the event log was capped and the list of every run the firm has ever
   done was not. Measured at a realistic firm - 54 runs over 18 engagements - the Runs panel
   grew to 4148px and the page to 4787, and a reader who scrolled to the last run found that
   clicking it opened a panel 3570px above them. The cap is a max-height, so at the three
   runs this machine has it changes nothing: measured both ways, 305px either way.

   There is a second reason to cap, and it is worth keeping apart from the first: a list
   this build decides can still be long because this build made it long - 118 nodes of the
   design, eleven seams with a paragraph each. Those are capped too, and they are the two
   the first version got right. What it missed is everything in the other group, which is
   short today and short only because this machine has three runs on it.

   These are the only panels that scroll, and the shadows below say so. Every other panel is
   as tall as what it holds, so a shadow on one means there is genuinely more rather than
   meaning the grid was short. */
.card.stream>.body{max-height:26rem;overflow:auto;
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
.metric{background:var(--surface);padding:var(--s3) var(--s4) var(--s4);position:relative;
 transition:background .2s var(--ease)}
.metric:hover{background:var(--surface-2)}
/* A short rule under each figure in the figure's own colour, so the row of six reads as
   six instruments rather than six cells. */
.metric::after{content:"";position:absolute;left:var(--s4);right:var(--s4);bottom:0;height:3px;
 border-radius:3px 3px 0 0;opacity:.6;
 background:linear-gradient(90deg,var(--accent),color-mix(in srgb,var(--accent) 15%,transparent))}
.metric.good::after{background:linear-gradient(90deg,var(--good),color-mix(in srgb,var(--good) 15%,transparent))}
.metric.warn::after{background:linear-gradient(90deg,var(--gold),color-mix(in srgb,var(--gold) 15%,transparent))}
.metric.bad::after{background:linear-gradient(90deg,var(--bad),color-mix(in srgb,var(--bad) 15%,transparent))}
.metric .k{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);display:block;margin-bottom:.45rem;font-weight:600}
.metric .v{font-size:2.25rem;font-weight:600;letter-spacing:-.035em;line-height:1;
 display:block;color:var(--navy);font-variant-numeric:lining-nums tabular-nums;
 animation:rise .6s var(--ease) both}
.metric .v small{font-size:.9rem;font-weight:500;color:var(--ink-3);letter-spacing:0;margin-left:.15rem}
.metric .c{display:block;margin-top:.45rem;font-size:var(--t-xs);color:var(--ink-3);line-height:1.45}
.metric.good .v{color:var(--good)}.metric.warn .v{color:var(--warn)}.metric.bad .v{color:var(--bad)}
/* The figures a page is about, set on the chrome's own navy so the first thing seen is the
   first thing read. White figures, pale-blue labels, the brand's pale colours for the three
   tones - every one measured against the navy rather than the paper (P171). */
.metrics.hero{background:linear-gradient(135deg,#123b50,var(--navy) 55%,#0a2634);
 border-color:var(--navy);box-shadow:var(--shadow-lift)}
.metrics.hero .metric{background:transparent;box-shadow:inset 1px 0 0 rgba(255,255,255,.07)}
.metrics.hero .metric:hover{background:rgba(255,255,255,.04)}
.metrics.hero .k{color:color-mix(in srgb,var(--brand-p3) 85%,white)}
.metrics.hero .v{color:#fff}
.metrics.hero .v small,.metrics.hero .c{color:color-mix(in srgb,var(--brand-s5) 72%,var(--brand-p3))}
.metrics.hero .metric.good .v{color:var(--brand-p4)}
.metrics.hero .metric.warn .v{color:color-mix(in srgb,var(--gold) 78%,white)}
.metrics.hero .metric.bad .v{color:color-mix(in srgb,var(--brand-s2) 45%,white)}
.metrics.hero .metric::after{opacity:.95}
.metrics.hero .metric.good::after{background:linear-gradient(90deg,var(--brand-p4),transparent)}

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
/* The id line under a row: an engagement, a scope and a run id, which is read and
   copied. It was set in the decorative grey at 2.86:1 - under the floor this sheet
   states for itself, and in the token it says nothing a person has to read uses. */
.r .sub.mono{font-size:.74rem;letter-spacing:0;color:var(--ink-3)}
.r .d{display:block;color:var(--ink-3);font-size:var(--t-xs);margin-top:.15rem;
 white-space:normal;line-height:1.45}
.r.head{padding-bottom:.4rem;border-bottom:1px solid var(--line)}
.r.head span{font-size:var(--t-label);letter-spacing:.14em;text-transform:uppercase;
 color:var(--ink-3);font-weight:600}
.r.link,.r.pick{cursor:pointer;border-radius:var(--radius-sm);
 padding-left:.6rem;padding-right:.6rem;margin:0 -.6rem;
 transition:background .16s var(--ease),box-shadow .16s var(--ease)}
.r.link:hover,.r.pick:hover{background:var(--surface-2);box-shadow:inset 2px 0 0 var(--line)}
.r.link.on,.r.pick.on{box-shadow:inset 3px 0 0 var(--accent);
 background:linear-gradient(90deg,var(--accent-soft),color-mix(in srgb,var(--accent-soft) 35%,transparent))}

/* An engagement is a name, a state, and five things you can do to it. The first two own
   the first line; the rest sit under them, so a client with a long name is not the thing
   that has to give way. */
.r.engagement{flex-wrap:wrap;align-items:flex-start;padding:.7rem 0 .6rem;row-gap:.35rem}
.r.engagement .lbl{flex:1 1 14rem}
.r.engagement>.pill{margin-top:.15rem}
.r.engagement .acts{flex:1 0 100%;display:flex;flex-wrap:wrap;gap:.25rem;justify-content:flex-end;
 align-items:center}
.r.engagement .acts button.quiet,.r.engagement .acts .btn.quiet{padding:.3rem .5rem;font-size:var(--t-xs);color:var(--ink-3)}
.r.engagement .acts button.quiet:hover,.r.engagement .acts .btn.quiet:hover{color:var(--navy)}

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
/* Something still happening is the one state a still page cannot show with colour alone:
   the dot on a running or waiting pill breathes. The same reduced-motion rule stops it. */
.pill.accent .dot,.pill.warn .dot{animation:breathe 2.2s var(--ease) infinite}
@keyframes breathe{0%,100%{box-shadow:0 0 0 2px color-mix(in srgb,currentColor 18%,transparent)}
 50%{box-shadow:0 0 0 5px color-mix(in srgb,currentColor 0%,transparent)}}

/* ---------------------------------------------------------------- bar */
.bar{height:.4rem;border-radius:99px;background:var(--surface-sunken);overflow:hidden;
 box-shadow:inset 0 0 0 1px var(--line-soft)}
.bar>i{display:block;height:100%;border-radius:99px;position:relative;overflow:hidden;
 background:linear-gradient(90deg,var(--accent),color-mix(in srgb,var(--accent) 60%,var(--brand-p3)));
 transition:width .7s var(--ease)}
.bar.good>i{background:linear-gradient(90deg,var(--good),color-mix(in srgb,var(--good) 60%,var(--brand-p4)))}
.bar.warn>i{background:linear-gradient(90deg,var(--gold),color-mix(in srgb,var(--gold) 65%,var(--brand-s5)))}
.bar.bad>i{background:linear-gradient(90deg,var(--bad),color-mix(in srgb,var(--bad) 65%,var(--brand-p3)))}
/* A light passing along the filled part, slowly: the bar is measuring something that is
   still moving. */
.bar>i::after{content:"";position:absolute;inset:0;transform:translateX(-100%);
 background:linear-gradient(90deg,transparent,rgba(255,255,255,.38),transparent);
 animation:shimmer 2.8s var(--ease) infinite}
@keyframes shimmer{to{transform:translateX(100%)}}

/* ---------------------------------------------------------------- controls */
/* `button` and `.btn` together, in every rule rather than only this one. `.btn` exists so
   an anchor can look like a button - which is what a control that is also a link has to be,
   and the engagement row's `files` and `settings` are exactly that. Half the rules below
   named only `button`, so an anchor got the base style and none of the modifiers: a quiet
   link rendered as a solid button beside the quiet buttons it sits with. */
button,.btn{font:600 var(--t-sm)/1 var(--sans);background:var(--surface);color:var(--navy);
 border:1px solid var(--line-strong);border-radius:var(--radius-sm);
 padding:.5rem .85rem;cursor:pointer;letter-spacing:.005em;
 box-shadow:0 1px 1px rgba(12,46,63,.04);
 transition:background .16s var(--ease),border-color .16s var(--ease),
  box-shadow .16s var(--ease),transform .12s var(--ease)}
button:hover,.btn:hover{background:var(--surface-2);border-color:var(--accent);
 box-shadow:0 1px 2px rgba(12,46,63,.08)}
button:active,.btn:active{transform:translateY(1px);box-shadow:none}
button.primary,.btn.primary{background:linear-gradient(180deg,#17465f,var(--navy));color:#fff;
 border-color:var(--navy);box-shadow:0 1px 2px rgba(12,46,63,.24)}
button.primary:hover,.btn.primary:hover{background:linear-gradient(180deg,#1b5271,#103a4f);border-color:var(--navy);
 box-shadow:0 6px 14px -6px rgba(12,46,63,.55);transform:translateY(-1px)}
/* The one button that ends something. Plum rather than red: it is the palette's colour for
   a problem, and a dialog that turns red reads as an alarm somebody bolted on. */
button.primary.danger,.btn.primary.danger{background:linear-gradient(180deg,#633553,var(--bad));border-color:var(--bad);
 box-shadow:0 1px 2px rgba(81,42,68,.26)}
button.primary.danger:hover,.btn.primary.danger:hover{background:linear-gradient(180deg,#713d60,#46243b);border-color:var(--bad)}
button.quiet,.btn.quiet{background:transparent;border-color:transparent;color:var(--accent-ink);
 padding:.4rem .55rem;box-shadow:none}
button.quiet:hover,.btn.quiet:hover{color:var(--navy);background:var(--accent-soft);border-color:transparent}
button.ghost,.btn.ghost{background:transparent;color:var(--ink-2);box-shadow:none}
button.ghost:hover,.btn.ghost:hover{background:var(--surface-2);color:var(--navy)}
button.small,.btn.small{padding:.32rem .6rem;font-size:var(--t-xs)}
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
/* A field holding a file path, sitting on a row beside its buttons. Sized in `ch`
   because the thing being typed is text of a known-ish length, and because a width in
   rem would shrink proportionally as the fluid root grows - the opposite of what it is
   for. `flex` rather than a fixed width so the row still collapses on a narrow window. */
input.path{width:auto;flex:1 1 30ch;min-width:24ch;margin:0}

/* ---------------------------------------------------------------- states */
.card .body:has(>.empty:only-child){display:flex;align-items:center;justify-content:center}
.empty{padding:var(--s6) var(--s4);text-align:center;color:var(--ink-3);font-size:var(--t-xs);
 line-height:1.55;max-width:44ch;margin:0 auto}
/* The title, which is the first thing in every empty state and nothing else. It used to
   be every `b` inside one, and the Activity console's "here is how one starts" puts a `b`
   mid-sentence to name a control - so "files" and "Waiting on a person" rendered as
   display-serif headings on their own lines, with the sentence's full stop orphaned on the
   line after. A rule meant for the one element at the top was being applied to emphasis. */
.empty>b:first-child{display:block;color:var(--navy);font:400 var(--t-subtitle)/1.3 var(--serif);
 margin-bottom:.35rem;letter-spacing:-.005em}
/* And a `b` anywhere else in one is emphasis, at the size of the text around it. */
.empty b{font-weight:600;color:var(--ink-2)}
.note{font-size:var(--t-xs);color:var(--ink-3);margin-top:var(--s3);line-height:1.5}
/* A note that follows straight on from what it is about, rather than closing a section. */
.note.tight{margin-top:0}
.skel{height:.7rem;border-radius:3px;background:linear-gradient(90deg,var(--surface-2),var(--surface-sunken),var(--surface-2));
 background-size:200% 100%;animation:sh 1.4s ease-in-out infinite;margin:.6rem 0}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){
 *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;
  transition-duration:.001ms!important}
}

/* --------------------------------------------------- narrower than a desk */
/* Three columns need the width for three columns. Below that there is one, and the rest
   of the chrome stops trying to sit on a single line.

   It used to carry three more declarations - `overflow:auto` on html and body,
   `overflow:visible` on `.wrap`, and `max-height:none` on a card's body - and all three
   undid rules that P142 removed. Nothing on this page has had an overflow to undo since,
   and `.card .body` loses to `.card.stream>.body` on specificity, so the one body that is
   still capped stayed capped either way. Verified by applying all three at the top of the
   sheet and measuring: the stream's cap read 377px before and 377px after.

   What this block is about is the column count, which is a question about width. The
   height rule that used to sit below it is gone for the same reason - see the note there. */
@media (max-width:1100px){
 .board{display:block!important}
 .board>.card{margin-bottom:var(--s3)}
 .chrome{flex-wrap:wrap;gap:.3rem .8rem}
 .page-head{flex-direction:column;align-items:flex-start;gap:.2rem}
}

/* ---------------------------------------------------- shorter than a desk */
/* There is no rule here any more, and that is the point.

   P136 added one: below 760px of viewport the board became a single column and the page
   scrolled, because at a laptop's height every panel in a six-row grid was a peephole -
   "Getting set up" measured at 35% of its own content, three steps of eleven. That fixed
   the symptom at one size.

   P142 fixed the cause at every size: the board's rows are as tall as what is in them, so
   a short screen simply shows fewer of them and scrolls, exactly as a tall one does with
   more content. Measured with the old block applied and removed, the answer was identical -
   the same two panels scrolled either way, and those two are streams.

   It also made a claim it should not have: height decided the *column count*, and how many
   columns fit is a question about width. A 1366x600 laptop is a wide screen and keeps its
   three. The width rule above is the one that was always about columns. */

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
/* A row that introduces the list under it: the count, the state, no rule beneath. */
.r.lede{border-bottom:0;padding:0 0 var(--s3)}
/* A textarea holding a document rather than a sentence. */
.code-area{height:min(20rem,40vh);font-family:var(--mono);font-size:var(--t-sm)}
/* One step down from body, for a line that explains a control beside it. */
.sm{font-size:var(--t-sm)}
.field{margin:0 0 var(--s3)}
.field .hint{font-size:var(--t-xs);color:var(--ink-3);margin:0 0 var(--s1);line-height:1.45}
.field select{width:100%;padding:.5rem .65rem}
.field input,.field textarea,.field select{margin-bottom:var(--s1)}
/* A form with a shape. Fields pair up, one that carries a path or a sentence takes the
   width, and the gaps are the same gaps as everywhere else - a dialog whose spacing was
   chosen by eye is most of what makes a dialog look like an internal tool. */
.cols.two.ask{gap:0 var(--s5);margin-bottom:var(--s2)}
.cols.two.ask>.field.wide{grid-column:1 / -1}
/* The qualifier inside something set in caps, put back into sentence case: a label
   reading "EXCEL MODEL TEMPLATE - OPTIONAL, AND NOT THE AI MODEL" is a label nobody
   finishes. Not scoped to `label`, because a section heading takes a qualifier the same
   way and the activity console was writing this out by hand to get it. */
/* A qualifier beside a label - "optional, and not the AI model". It changes what the
   field means, so it is read, and it was set in the decorative grey at 2.86:1. */
.aside{text-transform:none;letter-spacing:0;color:var(--ink-3);font-weight:400}

/* ---------------------------------------------------------------- review panel */
.excerpt{font-family:var(--mono);font-size:var(--t-sm);line-height:1.6;white-space:pre-wrap;
 background:var(--surface-sunken);border-radius:0 var(--radius-sm) var(--radius-sm) 0;padding:.75rem .9rem;
 margin:.25rem 0 var(--s3);box-shadow:inset 3px 0 0 var(--accent);color:var(--ink);
 max-height:14rem;overflow:auto}
/* Something said rather than something typed: a dialog quoting a document or a model's
   answer back, so it is set in the reading face and given the room a paragraph needs. */
.excerpt.said{max-height:min(22rem,45vh);font-family:var(--sans);font-size:var(--t-body)}
/* A path rather than a passage: one line, a button beside it, and the gold rule because
   it is a place on the machine and not something a model said. */
.excerpt.path{display:flex;gap:var(--s3);align-items:center;white-space:normal;
 box-shadow:inset 3px 0 0 var(--gold)}
.excerpt.path>span{flex:1;min-width:0;overflow-wrap:anywhere}
/* Somewhere to drop a client's files. Dashed because the border is an invitation rather
   than an edge, and it answers the keyboard as well as the mouse. */
.drop{border:2px dashed var(--line);border-radius:var(--radius);padding:var(--s5);
 text-align:center;color:var(--ink-3);margin:var(--s1) 0 var(--s3);cursor:pointer;
 background:var(--surface-2);
 transition:border-color .16s var(--ease),background .16s var(--ease)}
.drop:hover{border-color:var(--accent-line);background:var(--accent-soft)}
.drop b{color:var(--navy);font-weight:600}
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
/* A line under a section label, for a group of fields whose numbers need a sentence
   before somebody types in one. Beside `.section-label` rather than inside `.field`,
   because it is about the group and the fields in it are laid out as a grid. */
.section-note{font-size:var(--t-xs);color:var(--ink-3);line-height:1.45;
 margin:0 0 var(--s2);max-width:74ch}
.section-note b{color:var(--ink-2);font-weight:600}
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

/* A count in the chrome that is also the control. Somebody reads "12 need a person" and
   the next thing they want is those twelve, so the number is pressable rather than a
   fact to go and act on somewhere else. Styled to look pressable without becoming a
   button in a header that has no room for one: the gold is the same gold the count
   already used, and the dotted underline is the only thing added. */
/* Two classes the pages used to spell as inline colours, moved here so the colour of a
   thing is decided in one place and can be measured.

   `--gold` is the brand's accent and is not a text colour: at 2.63:1 on white it was
   the least readable thing on the Activity console, carrying the most important line
   on it. `--warn` is `--gold-ink`, the darkened gold made for exactly this, at 5.4:1.

   `.quiet-note` is for a line that sits beside something and is still read - where a
   step failed, the formula behind a finding, the checks that did not run. Those were
   in `--ink-4`, which this sheet reserves for a placeholder, a disabled control and a
   node no run reached. */
.wants-a-person{color:var(--warn)}
.quiet-note{color:var(--ink-3)}
/* A figure nobody has measured yet, where a figure would be. Quieter than a real
   one and still legible, because it is the answer rather than a stand-in for one. */
.not-measured{color:var(--ink-3)}
.chip{color:var(--gold);cursor:pointer;border-bottom:1px dotted currentColor;
 padding-bottom:1px;transition:color .15s var(--ease)}
.chip:hover,.chip:focus-visible{color:var(--navy);border-bottom-style:solid}
.chip:focus-visible{outline:2px solid var(--gold);outline-offset:2px;border-radius:2px}
.toggle{display:inline-flex;align-items:center;gap:.4rem;font-size:var(--t-xs);color:var(--ink-3);
 cursor:pointer;user-select:none;text-transform:none;letter-spacing:0;margin:0;font-weight:400}
.toggle input{width:auto;margin:0}

/* A panel's own find box. Sits under the header's why-line, so the thing that narrows a
   list is beside the sentence saying what the list is. */
.filter{display:flex;align-items:center;gap:var(--s2);margin-top:var(--s2)}
.filter input{margin:0;flex:1 1 auto;min-width:0;padding:.3rem var(--s2);font-size:var(--t-xs)}
.filter .btn{flex:0 0 auto}

/* An engagement, and the runs behind it. The group header is the line an analyst reads
   first; its runs are indented under it so the nesting is visible without a rule. */
/* A line that has just arrived in the live feed slides in on the accent wash and
   settles to the paper, so the eye is taken to what changed without a count to read. */
#feed>.r{animation:arrive .6s var(--ease) both}
@keyframes arrive{from{opacity:0;transform:translateY(-.3rem);background:var(--accent-soft)}
 to{opacity:1;transform:none;background:transparent}}
.grp{margin:0 0 var(--s2)}
.grp-head{display:flex;align-items:baseline;gap:var(--s2);padding:.3rem .2rem .2rem;
 border-bottom:1px solid var(--line)}
.grp-head b{font-size:var(--t-sm);color:var(--navy)}
.grp-head .sub{margin-left:auto;text-align:right;white-space:nowrap}
.grp-runs{padding-left:var(--s2)}

/* ---------------------------------------------------------------- steps */
/* Seven marks in a column read as a list of unrelated things until a rule joins them.
   The rail is the whole difference between "here are seven tasks" and "here is where you
   are in one sequence", and it costs one pseudo-element: drawn from each mark to the next,
   never after the last, and carrying the colour of the step above it so the finished part
   of the run is visibly the finished part.

   A finished step costs one line and an unfinished one costs three. Five done and two
   left used to fill the panel evenly, which put most of the ink on the part nobody has to
   read again. */
/* Capped at a readable measure. Inside the board's three columns the panel is narrower
   than this and nothing changes; in the single-column fallback a laptop and a narrow
   window both get, the rows would otherwise run the full width of the screen and put a
   step's button a thousand pixels from the step it belongs to. */
.steps{display:flex;flex-direction:column;--mark:1.6rem;max-width:84ch}
.step{display:flex;gap:var(--s3);align-items:flex-start;padding:var(--s2) var(--s3);
 border-radius:var(--radius-sm);position:relative;
 transition:background .16s var(--ease)}
/* Centred on the mark by construction rather than by two numbers that happen to agree:
   the step's own left padding, plus half a mark. Change --mark and the rail follows. */
.step::before{content:"";position:absolute;
 left:calc(var(--s3) + var(--mark) / 2);top:calc(var(--s2) + var(--mark));
 bottom:calc(var(--s2) * -1);width:1px;background:var(--line);
 transition:background .16s var(--ease)}
.step:last-child::before{display:none}
.step.done::before{background:var(--good-line)}
.step.now{background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent-line)}
.step .mark{width:var(--mark);height:var(--mark);border-radius:99px;flex:none;margin-top:.05rem;
 display:grid;place-items:center;font-size:var(--t-xs);font-weight:600;position:relative;
 z-index:1;font-variant-numeric:tabular-nums;
 background:var(--surface);color:var(--ink-3);box-shadow:inset 0 0 0 1px var(--line)}
.step.done .mark{background:var(--good-soft);color:var(--good);box-shadow:inset 0 0 0 1px var(--good-line)}
/* The one the person is on: filled navy and ringed off the wash behind it, so it reads as
   the position on the rail rather than as one more coloured dot. */
.step.now .mark{background:linear-gradient(180deg,#17465f,var(--navy));color:#fff;
 box-shadow:0 0 0 3px var(--accent-soft),0 1px 2px rgba(12,46,63,.24)}
.step>span:not(.mark):not(.go){flex:1;min-width:0}
.step .t{display:block;font-size:var(--t-sm);color:var(--navy);font-weight:600}
.step.done .t{color:var(--ink-3);font-weight:500}
.step.now .t{font-size:var(--t-subtitle);letter-spacing:-.006em}
.step .d{display:block;font-size:var(--t-xs);color:var(--ink-3);margin-top:.1rem;line-height:1.5}
/* Confirmation, not instruction: a finished step is a receipt, so its title and its one
   line of detail share a line rather than taking two.

   Measured rather than guessed. At a 600px viewport - a laptop with browser chrome, which
   is the shape of the machine this is moving to - the "Getting set up" panel was showing
   35% of its own content: three of eleven steps, in the panel a first day is spent in.
   Half of what it was scrolling past was the detail under steps already done. */
.step.done>span:not(.mark):not(.go){white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.step.done .t{display:inline}
.step.done .d{display:inline;margin-top:0}
.step.done .d::before{content:"·";margin:0 .4rem;color:var(--line)}
.step .go{margin-left:auto}

/* The count, set as a figure. The panel had no anchor at all - its largest element was a
   heading, so the eye had nowhere to land and the screen read as reference material. */
.progress{display:flex;align-items:baseline;gap:var(--s3);margin:0 0 var(--s2)}
.progress .n{font:400 var(--t-display)/1 var(--serif);color:var(--navy);letter-spacing:-.02em;
 font-variant-numeric:lining-nums tabular-nums}
.progress .of{font-size:var(--t-sm);color:var(--ink-3);line-height:1.4}
.progress .of b{display:block;color:var(--navy);font-weight:600}
.progress .done{margin-left:auto;text-align:right}

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
/* The key is the nodes. It used to be five squares coloured by hand in the markup, and
   measured against the nodes they stood for, all five disagreed - failed was drawn as a
   solid plum block where the node is pale pink, running as solid blue where the node is
   pale blue, touched as solid grey where the node is near-white. The map's key was
   repaired for exactly this and says why: a key whose swatches are a second copy of the
   drawing's rules is a key that drifts from the drawing.

   The fifth state is said rather than drawn. A node the run never reached has no box -
   that is the whole of what it looks like - and drawing a bordered square for it was how
   the two answers this panel says it matters most not to confuse came to look alike. */
.legend .node{cursor:default}
.legend-note{color:var(--ink-3)}
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
/* An absent figure says so in words, and the words are read. They were set in `--ink-4`,
   which this sheet keeps for a placeholder - and at 13.8px in the column where a figure
   goes, "not yet" is not a placeholder, it is the answer: measured at 2.86:1, under the
   floor, on the panel whose whole job is to say what has not been measured. */
const pct = v => (v === null || v === undefined)
  ? '<span class="not-measured">not yet</span>' : (v * 100).toFixed(1) + '%';
const num = (v, dash = 'not yet') => (v === null || v === undefined)
  ? '<span class="not-measured">' + dash + '</span>' : esc(v);
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

/* Which events may travel. A press climbs: you click the text inside a row and the row is
   what acts. A field's own events do not - `change` and `input` belong to the control that
   fired them, and letting them climb would run a row's action on every keystroke typed
   into a box that happens to sit inside it. So a field's action is written on the field.

   This table is also the list of events a page may reach a handler through at all, which
   is the half that was missing: a field had nowhere to go, so three of them were wired
   with `oninput=` and `onchange=` instead - and the six tests that forbid wiring a handler
   inline were all looking for the word `onclick`. */
const CLIMBS = {click: true, keydown: true, change: false, input: false};

function _fire(ev) {
  const el = CLIMBS[ev.type]
    ? ev.target.closest('[data-act]')
    : (ev.target.matches && ev.target.matches('[data-act]') ? ev.target : null);
  if (!el || !ACTIONS[el.dataset.act]) return;
  if (ev.type === 'keydown') {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    if (ev.target.closest('input,textarea,select')) return;
  }
  /* Only a press is cancelled. A `change` has already happened by the time it is heard,
     and stopping an `input` would take it from everything else listening, the browser's
     own work on the field included. */
  if (CLIMBS[ev.type]) {
    ev.preventDefault();
    ev.stopPropagation();
  }
  ACTIONS[el.dataset.act](el.dataset, el, ev);
}
for (const kind of Object.keys(CLIMBS)) document.addEventListener(kind, _fire);

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
/* `refused: true` on every one of them, because the question a caller asks is "did the
   server answer" and not "did it answer with a code". Only some refusals carry a
   structured diagnostic; all of them came back from a server that was reached. A page
   that tests for the code instead reports a reachable server as unreachable, which is
   what the Setup page did on the one machine it most had to work on. */
async function refusal(response) {
  try {
    const body = await response.json();
    const d = ((body.detail || {}).refused || [])[0];
    if (d) return { refused: true, text: d.what_now || d.detail, code: d.code + ' — ' + d.detail };
    return { refused: true,
             text: typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail) };
  } catch (e) {
    return { refused: true, text: response.status + ' ' + response.statusText };
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
      <div class="body">${body ? `<div class="excerpt said">${esc(body)}</div>` : ''}${fields.map((f, n) => `<div class="field">
        <label for="ask_${n}">${esc(f.label)}${f.required ? '' : ' <span class="aside">(optional)</span>'}</label>
        ${f.hint ? `<p class="hint">${esc(f.hint)}</p>` : ''}
        ${f.kind === 'select'
          ? `<select id="ask_${n}">${(f.options || []).map(o => `<option value="${esc(o.value)}"${o.value === f.value ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`
          : f.kind === 'textarea'
            ? `<textarea id="ask_${n}" rows="3" placeholder="${esc(f.placeholder || '')}">${esc(f.value || '')}</textarea>`
            : `<input id="ask_${n}" value="${esc(f.value || '')}" placeholder="${esc(f.placeholder || '')}">`}
      </div>`).join('')}${note ? `<p class="note tight">${esc(note)}</p>` : ''}</div>
      <div class="foot"><button class="quiet" data-act="cancel">Cancel</button>
       <button class="primary${danger ? ' danger' : ''}" data-act="ok">${esc(ok)}</button></div>
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

/* `/` goes to the page's find box, wherever the page keeps it.

   The whole-design view has answered `/` since P49 and says so in its own legend, and the
   two consoles with a find box answered nothing - so the same keystroke meant "find" in
   one view and typed a slash into the next. A shortcut that is true in one place and not
   in another is worse than no shortcut, so it is written once here and a page gets it by
   having a `.filter` at all.

   Three things it refuses. Typing into a field is typing, not a shortcut. A dialog is
   modal, so the box behind it is not where a keystroke should go. And the map is open
   over the whole page when `#dmap` is `on`, where its own handler owns the key. */
document.addEventListener('keydown', e => {
  if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest && e.target.closest('input,textarea,select,[contenteditable]')) return;
  if (document.querySelector('.modal') || document.querySelector('#dmap.on')) return;
  const box = document.querySelector('.filter input');
  if (!box) return;
  e.preventDefault();
  box.focus();
  box.select();
});

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
