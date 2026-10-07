# ruff: noqa: E501 - a browser view held in strings; wrapping it makes it harder to read.
"""The whole design, painted with what one run did.

The Run trace panel lists the nodes a run touched, grouped, without their edges - which
answers "what did it do" and not "where in the system did it happen". This is the other
view: every node of the blueprint, in the blueprint's own positions, with the edges between
them, and each node bordered by what happened there on this run.

**The positions are the blueprint's.** `graph/architecture.json` carries the x and y the
design of record puts each node at, exported from the same file the assertions run over, and
covered by the same digest - so this is the design's own picture rather than a second
drawing of it that has to be kept in step by hand. A node moved in the blueprint moves here
on the next export, and a blueprint edited without one fails a test.

**What it is for.** Standing in front of a halted run and asking where it stopped, what it
had already passed, and what never ran at all. The border carries that: mint for passed,
plum for failed, the accent for running, a hairline for touched, and a dashed outline for
the hundred-odd nodes a given run never reaches. Clicking one says what happened there, in
the events the run recorded against it.
"""

from __future__ import annotations

__all__ = ["MAP_HTML", "MAP_JS", "MAP_STYLE"]

MAP_STYLE = """
/* ---------------------------------------------------------------- the map */
#dmap{position:fixed;inset:0;z-index:70;display:none;flex-direction:column;
 background:var(--bg)}
#dmap.on{display:flex;animation:dmapin .18s var(--ease)}
@keyframes dmapin{from{opacity:0}to{opacity:1}}
#dmap .map-top{flex:none;display:flex;align-items:baseline;gap:var(--s5);
 padding:var(--s3) var(--s6);border-bottom:1px solid var(--line);background:var(--surface);
 box-shadow:var(--shadow)}
#dmap .map-top h2{font:400 var(--t-title)/1.2 var(--serif);margin:0;color:var(--navy);
 letter-spacing:-.012em;white-space:nowrap}
#dmap .map-top h2 .of{font:600 var(--t-label)/1 var(--sans);letter-spacing:.08em;
 text-transform:uppercase;color:var(--ink-3);margin-left:.6rem;
 font-variant-numeric:tabular-nums}
#dmap .map-top .why{margin:.15rem 0 0;font-size:var(--t-xs);color:var(--ink-3)}
#dmap .map-top .head{min-width:0}
#dmap .map-top .head .why{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Two ranks, separated by a rule rather than by a wider gap: what moves the view, and the
   way out of it. */
#dmap .map-tools{margin-left:auto;display:flex;align-items:center;gap:var(--s2);flex:none}
#dmap .map-tools .sep{width:1px;align-self:stretch;background:var(--line-soft);
 margin:0 var(--s1)}
/* The chevrons were about 20px square at the fluid root's floor, under the 24px minimum
   and set a tenth of a rem apart, so the targets overlapped. */
#dmap .seg button,#dmap .zoom button{min-width:1.75rem;min-height:1.75rem}
#dmap .zoom{display:inline-flex;align-items:center;gap:.15rem;border:1px solid var(--line-strong);
 border-radius:var(--radius-sm);background:var(--surface);overflow:hidden}
#dmap .zoom button{border:0;border-radius:0;box-shadow:none;padding:.4rem .6rem;background:transparent}
#dmap .zoom button:hover{background:var(--surface-2)}
#dmap .zoom .lvl{padding:0 .5rem;font-size:var(--t-xs);color:var(--ink-3);min-width:3.4rem;
 text-align:center;font-variant-numeric:tabular-nums}
#dmap .side{position:relative}

#dmap .map-body{flex:1;min-height:0;display:flex}
/* The ground the sheet lies on, and the frame it is seen through. Both insets are on
   the stage, so the shading stays at the edge of the window while the drawing moves. */
#dmap .stage{flex:1;min-width:0;position:relative;overflow:hidden;cursor:grab;
 touch-action:none;
 background:var(--surface-sunken);
 box-shadow:inset 0 1px 0 var(--line-soft),
  inset 0 30px 46px -34px color-mix(in srgb,var(--navy) 20%,transparent),
  inset 0 -30px 46px -34px color-mix(in srgb,var(--navy) 14%,transparent)}
#dmap .stage.dragging{cursor:grabbing}
/* The sheet: paper, a hairline, and enough shadow to sit on the ground rather than in it. */
#dmap .pan{position:absolute;top:0;left:0;transform-origin:0 0;
 background:var(--bg);box-shadow:0 0 0 1px var(--line-soft),var(--shadow)}
/* The blueprint's own module - a row and a column - ruled faintly, and gone at a zoom
   where it would only alias. */
#dmap:not(.far) .pan{background-image:
 repeating-linear-gradient(0deg,var(--line-soft) 0 1px,transparent 1px 152px),
 repeating-linear-gradient(90deg,var(--line-soft) 0 1px,transparent 1px 198px)}
/* Stepping is the one thing that should move, and it was the one thing that cut: eight
   instantaneous jumps, median 396px, across a view whose whole thesis is that a run is a
   sequence. Dragging stays one-to-one. */
#dmap .pan{transition:transform 0s}
#dmap .pan.gliding{transition:transform .34s var(--ease)}
#dmap .stage.dragging .pan{transition:none;will-change:transform}
#dmap .pan svg{position:absolute;top:0;left:0;pointer-events:none;overflow:visible}
/* The route the run took, over the design rather than in it. A dotted trail reads as
   "went here next" without competing with the solid lines of the structure. */
#dmap #dmap-path path{fill:none;stroke:var(--navy);stroke-width:2;stroke-opacity:.5;
 stroke-linecap:round;stroke-dasharray:1 7}
#dmap #dmap-path path.off{stroke-opacity:.62}
#dmap.far #dmap-path path{stroke-width:3;stroke-opacity:.6}
#dmap.focused #dmap-path{opacity:.15}

/* A node of the design, as the blueprint places it. */
#dmap .mn{--edge:var(--line);--wash:var(--surface);--mark:transparent;
 position:absolute;width:178px;height:52px;padding:.4rem .5rem .4rem .7rem;
 border-radius:var(--radius-sm);overflow:hidden;
 display:flex;flex-direction:column;justify-content:center;
 background:var(--wash);border:1px solid var(--edge);color:var(--ink-3);
 font-size:var(--t-sm);line-height:1.25;text-align:left;box-shadow:none;
 contain:layout paint style;
 transition:border-color .12s var(--ease),background .12s var(--ease),box-shadow .12s var(--ease)}
/* The mark is a rule on the leading edge, which is this console's own way of saying what
   a block is - `.excerpt`, `.diag .d-row` and the current link all do it. Drawn as a
   pseudo-element rather than an inset shadow so that box-shadow stays free for the rings. */
#dmap .mn::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
 background:var(--mark);border-radius:var(--radius-sm) 0 0 var(--radius-sm)}
/* The page's own button rules reach in here: a 1px nudge on :active would take the node
   off the blueprint's grid, and the shared focus ring would change its corner radius. */
#dmap .mn:active{transform:none}
#dmap .mn .nm{display:block;color:var(--ink-2);font-weight:600;font-size:var(--t-sm);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* The id inherits the page's `button{font-weight:600}` unless it says otherwise, which is
   why it read heavy; and --ink-4 is documented as being below the floor for anything a
   person has to read, which an id that gets pasted into a message is. */
#dmap .mn .id{display:block;font-family:var(--mono);font-size:var(--t-label);
 font-weight:400;color:var(--ink-3);letter-spacing:-.01em;
 margin-top:.05rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Never reached: drawn as an outline, because a node a run did not touch is not a node
   that passed - the one distinction this whole view exists to make. The hairline was
   navy at 8%, which is invisible at full size and gone by 60% zoom, on the state that is
   most of the canvas. */
#dmap .mn.notreached,#dmap .mn.pending{--edge:var(--line);border-style:dashed;
 --wash:transparent}
#dmap .mn.notreached .nm,#dmap .mn.pending .nm{color:var(--ink-3);font-weight:400}
/* Downstream of where it stopped, and never reached: the work this run did not get to.
   Gold is the brand's colour for "attention", which is what these are. */
#dmap .mn.blocked{--edge:var(--warn-line);--wash:var(--warn-soft);--mark:var(--gold);
 border-style:dashed}
#dmap .mn.blocked .nm{color:var(--warn)}
#dmap .mn.used{--edge:var(--line-strong);--mark:var(--line-strong)}
#dmap .mn.used .nm{color:var(--ink)}
#dmap .mn.passed{--edge:var(--good-line);--wash:var(--good-soft);--mark:var(--good)}
#dmap .mn.passed .nm{color:var(--good)}
/* Failed is the one state a person is looking for, so it is the one that is allowed to
   sit above the paper. */
#dmap .mn.failed{--edge:var(--bad);--wash:var(--bad-soft);--mark:var(--bad);
 box-shadow:var(--shadow)}
#dmap .mn.failed .nm{color:var(--bad)}
#dmap .mn.active{--edge:var(--accent-line);--wash:var(--accent-soft);--mark:var(--accent)}
#dmap .mn.active .nm{color:var(--accent-ink)}
/* Running is the only state that is still happening, and a still picture cannot say so
   with a colour that three other things also use. The global reduced-motion rule turns
   this off, which is why it is a CSS animation and not a timer. */
#dmap .mn.active::before{animation:mnpulse 1.8s var(--ease) infinite}
@keyframes mnpulse{0%,100%{opacity:1}50%{opacity:.35}}
/* What a run touched sits on the sheet; what it never reached is drawn on it. The same
   elevation the console gives a panel, and a faint light along the top edge, so the eight
   or twenty nodes that matter read as objects and the hundred that do not read as plan. */
#dmap .mn.used,#dmap .mn.passed,#dmap .mn.active,#dmap .mn.failed{box-shadow:var(--shadow);
 background-image:linear-gradient(180deg,color-mix(in srgb,var(--surface) 55%,transparent),transparent 65%)}
#dmap .mn.on{box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--accent),var(--shadow-lift)}
/* The order the run touched it in. A run is a sequence, and this is the only place the
   picture can say so. */
/* The console already has this object - `.step .mark` - so this is that one, wearing the
   node's own state. It used to be solid navy at weight 700 hanging over the border, which
   put eight of the loudest marks on the canvas on top of the colours they annotate.

   Inside the box, not over its corner. It sat at -.6rem/-.5rem - outside a node that
   clips its own overflow and paints under `contain` - so every number a run wrote on the
   sheet was a quarter-circle with nothing legible in it (P170). The badge now takes the
   top-right of the node and the name and id give it the column, so the one thing this
   view can say that the trace panel cannot - which way the run went - is readable. */
#dmap .mn .ord{position:absolute;top:.3rem;right:.3rem;min-width:1.3rem;height:1.3rem;
 padding:0 .3rem;border-radius:99px;background:var(--surface);color:var(--ink-2);
 font-size:var(--t-label);font-weight:600;line-height:1;display:none;place-items:center;
 font-variant-numeric:tabular-nums;letter-spacing:-.01em;
 box-shadow:inset 0 0 0 1px var(--line),0 1px 2px color-mix(in srgb,var(--navy) 10%,transparent)}
#dmap .mn[data-ord] .ord{display:grid}
#dmap .mn[data-ord] .nm,#dmap .mn[data-ord] .id{padding-right:1.8rem}
#dmap .mn.passed .ord{color:var(--good);box-shadow:inset 0 0 0 1px var(--good-line)}
#dmap .mn.active .ord{background:var(--accent);color:var(--surface);box-shadow:none}
#dmap .mn.failed .ord{background:var(--bad);color:var(--surface);box-shadow:none}
/* What a picked node is joined to, and what it is not. */
#dmap .mn.near{box-shadow:0 0 0 1px var(--surface),0 0 0 3px var(--accent-line)}
#dmap.focused .mn:not(.on):not(.near):not(:focus-visible){
 --edge:var(--line-soft);--mark:transparent;color:var(--ink-4)}
#dmap.focused .mn:not(.on):not(.near):not(:focus-visible) .nm{color:var(--ink-4)}
#dmap .mn.hit{box-shadow:0 0 0 2px var(--gold-ink)}
#dmap .mn:focus-visible{outline:3px solid var(--navy);outline-offset:3px;
 border-radius:var(--radius-sm)}
/* The key belongs on the drawing, where a draftsman puts it - and its swatches are the
   node's own rules rather than a second copy of them, which had already drifted: the node
   is dashed and the swatch was solid, on the one distinction this view is about. */
#dmap .plate{position:absolute;left:var(--s5);bottom:var(--s5);z-index:2;
 display:flex;flex-direction:column;gap:var(--s1);
 padding:var(--s3) var(--s4);border-radius:var(--radius);
 background:color-mix(in srgb,var(--surface) 92%,transparent);
 border:1px solid var(--line);box-shadow:var(--shadow-lift);
 backdrop-filter:blur(6px)}
#dmap .map-legend{display:flex;gap:var(--s1);flex-wrap:wrap}
#dmap .map-legend button{display:inline-flex;align-items:center;gap:.45rem;border:0;
 background:transparent;box-shadow:none;padding:.3rem .45rem;font-weight:400;
 font-size:var(--t-xs);color:var(--ink-3);min-height:1.75rem}
#dmap .map-legend button:hover{background:var(--surface-2);color:var(--navy)}
/* The swatch is a node: same custom properties, same leading mark, same dashed outline. */
#dmap .map-legend button i.mn{position:static;width:1.5rem;height:.85rem;padding:0;
 border-radius:var(--radius-xs);flex:none;display:block;contain:none;box-shadow:none;
 animation:none}
#dmap .map-legend button i.mn::before{width:2px;border-radius:var(--radius-xs) 0 0 var(--radius-xs)}
#dmap .map-legend button[aria-pressed="false"]{color:var(--ink-4);text-decoration:line-through}
#dmap .map-legend button[aria-pressed="false"] i.mn{opacity:.35}
/* The only place the map's keys are written down - P138 widened this line so somebody
   could find the two it had never mentioned. A list of shortcuts nobody can read is
   the same as not having written it. */
#dmap .plate .keys{font-size:var(--t-label);color:var(--ink-3);letter-spacing:.01em}
#dmap .plate .hidden-note:empty{display:none}
#dmap.hide-passed .mn.passed,#dmap.hide-failed .mn.failed,#dmap.hide-active .mn.active,
#dmap.hide-used .mn.used,#dmap.hide-notreached .mn.notreached,#dmap.hide-notreached .mn.pending,
#dmap.hide-blocked .mn.blocked,
#dmap.hide-blocked #dmap-edges path.f-blocked,#dmap.hide-blocked #dmap-edges path.t-blocked,
#dmap.hide-passed #dmap-edges path.f-passed,#dmap.hide-passed #dmap-edges path.t-passed,
#dmap.hide-failed #dmap-edges path.f-failed,#dmap.hide-failed #dmap-edges path.t-failed,
#dmap.hide-active #dmap-edges path.f-active,#dmap.hide-active #dmap-edges path.t-active,
#dmap.hide-used #dmap-edges path.f-used,#dmap.hide-used #dmap-edges path.t-used,
#dmap.hide-notreached #dmap-edges path.f-notreached,#dmap.hide-notreached #dmap-edges path.t-notreached{
 display:none}
#dmap .find{width:11rem;margin:0;padding:.45rem .6rem;font-size:var(--t-sm)}
#dmap .found{font-size:var(--t-xs);color:var(--ink-3);min-width:4.5rem}
#dmap .hidden-note{font-size:var(--t-xs);color:var(--ink-3)}
#dmap .seg{display:inline-flex;align-items:center;gap:.15rem;border:1px solid var(--line-strong);
 border-radius:var(--radius-sm);background:var(--surface);overflow:hidden}
#dmap .seg button{border:0;border-radius:0;box-shadow:none;padding:.4rem .55rem;background:transparent}
#dmap .seg button:hover{background:var(--surface-2)}
#dmap .seg .at{padding:0 .5rem;font-size:var(--t-xs);color:var(--ink-3);min-width:4.6rem;
 text-align:center;font-variant-numeric:tabular-nums}
#dmap .chips{display:flex;flex-wrap:wrap;gap:.3rem;margin:.1rem 0 var(--s3)}
#dmap .chips button{padding:.25rem .5rem;font-size:var(--t-xs);font-weight:400;
 color:var(--accent-ink);border-color:var(--line)}
#dmap .chips button:hover{border-color:var(--accent);background:var(--accent-soft)}
#dmap .chips .none{font-size:var(--t-xs);color:var(--ink-3)}
#dmap .said{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
 white-space:nowrap}
#dmap .mn:not(.on):not(.hit):hover{box-shadow:var(--shadow-lift)}
/* Far out, a two-line label is a smudge: the id alone, in type that survives the scale. */
/* Far out the state has to stop being a one-pixel border, because a one-pixel border at
   40% is a third of a pixel. The box fills instead, which survives any scale. */
#dmap.far .mn{padding:.3rem .45rem;border-width:0}
#dmap.far .mn .id{display:none}
#dmap.far .mn .nm{font-size:var(--t-display);line-height:1.1;font-weight:600}
#dmap.far .mn.notreached,#dmap.far .mn.pending{--wash:var(--surface-2);border-width:1px}
#dmap.far .mn.notreached .nm,#dmap.far .mn.pending .nm{visibility:hidden}
#dmap.far .mn.used{--wash:var(--line-strong)}
#dmap.far .mn.passed{--wash:var(--good)}
#dmap.far .mn.active{--wash:var(--accent)}
#dmap.far .mn.failed{--wash:var(--bad)}
/* Every state that means something happened fills solid at this zoom, because the labels
   are gone and the fill is the whole of what the drawing says. `blocked` was the one left
   out, so it kept the pale wash it wears up close - and measured 1.01:1 against
   `notreached`, the state that means the opposite. The two that read as nothing should be
   the two that *are* nothing. It takes the gold made for carrying text rather than the
   accent gold, because at this size the fill carries a white label. */
#dmap.far .mn.blocked{--wash:var(--warn)}
#dmap.far .mn.used .nm,#dmap.far .mn.passed .nm,#dmap.far .mn.active .nm,
#dmap.far .mn.failed .nm,#dmap.far .mn.blocked .nm{color:var(--surface)}
#dmap.far .mn::before{display:none}
/* Far out the box is a solid fill and the label is the id in display type; the number
   sits at the right edge, centred, on paper - every state, because the state rules above
   paint `active` and `failed` badges in the fill's own colour, which here is the box. */
#dmap.far .mn{background-image:none}
#dmap.far .mn .ord,#dmap.far .mn.active .ord,#dmap.far .mn.failed .ord{min-width:1.9rem;
 height:1.9rem;font-size:var(--t-subtitle);top:50%;right:.35rem;transform:translateY(-50%);
 background:var(--surface);color:var(--navy);box-shadow:none}
#dmap.far .mn[data-ord] .nm{padding-right:2.5rem}


#dmap.focused #dmap-edges path:not(.on){opacity:.1}
#dmap #dmap-edges path.on{stroke:var(--accent);stroke-width:2.4;stroke-opacity:.95}
/* The blueprint's own line grammar, without its colours: weight and dash carry the kind,
   so a guard, a declared loop and a masked crossing are each recognisable in both
   drawings. Ten kinds is too many for one channel, so the ones a reader asks about get a
   mark and the rest share the plain hairline. */
#dmap-edges path{stroke-width:1.1}
#dmap-edges path.live{stroke-width:1.8}
#dmap-edges path[data-kind="guard"],#dmap-edges path[data-kind="block"]{stroke-width:2.1}
#dmap-edges path[data-kind="human"]{stroke-width:2}
#dmap-edges path[data-kind="masked"]{stroke-width:2.6}
#dmap-edges path[data-kind="loop"]{stroke-width:1.9;stroke-dasharray:7 3 2 3}
#dmap-edges path[data-kind="data"]{stroke-dasharray:5 4}
#dmap-edges path[data-kind="record"]{stroke-dasharray:1 4}
#dmap-edges path[data-kind="pref"]{stroke-dasharray:2 5}
#dmap-edges path[data-kind="port"]{stroke-dasharray:2 6}
/* Far out an arrowhead is a blob and a dash is a smear. */
#dmap.far #dmap-edges path{marker-end:none;stroke-dasharray:none}

#dmap .band{position:absolute;height:1px;pointer-events:none;
 background:linear-gradient(90deg,transparent,var(--line) 4% 96%,transparent)}
#dmap .band.priv{height:1px;background:linear-gradient(90deg,transparent,
 color-mix(in srgb,var(--bad) 55%,transparent) 4% 96%,transparent)}
#dmap .band.priv::after{content:"";position:absolute;left:0;right:0;top:3px;height:1px;
 background:linear-gradient(90deg,transparent,
  color-mix(in srgb,var(--bad) 26%,transparent) 4% 96%,transparent)}
/* The rail: the names of the bands, at the margin of the window rather than of the sheet,
   so they are legible at any zoom and are never panned out of the frame. */
#dmap .rail{position:absolute;left:0;top:0;bottom:0;width:15rem;pointer-events:none;z-index:1;
 overflow:hidden}
/* The band headings that organise a hundred and eighteen nodes. `--ink-3` measured 4.47:1
   on the map's own paper - three hundredths under the floor, and on the hardest text in the
   sheet to read: the smallest size there is, in capitals, with wide tracking. A heading
   should not be at the edge of legible, so this is the secondary ink at about 7:1. */
#dmap .band-t{position:absolute;left:var(--s5);max-width:12.5rem;font-size:var(--t-label);
 letter-spacing:.14em;text-transform:uppercase;color:var(--ink-2);pointer-events:none;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
 font-weight:600;transform:translateY(-1.25rem)}
#dmap .band-t.priv{color:var(--bad)}
/* The one decorative use of the control edge, and so the one that does not follow it: this
   is a rule under a label, not the boundary of anything you can press. */
#dmap .band-t::before{content:"";position:absolute;left:0;right:-.6rem;bottom:-.35rem;
 height:1px;background:linear-gradient(90deg,var(--line),transparent)}
#dmap .band-t.priv::before{background:linear-gradient(90deg,
 color-mix(in srgb,var(--bad) 55%,transparent),transparent)}
/* A column names a region, not a line across one; giving it the band label's type made
   the two read as the same kind of thing, and it had no rule under it at all. */
#dmap .col-t{position:absolute;font-size:var(--t-label);letter-spacing:.06em;
 color:var(--ink-3);pointer-events:none;white-space:nowrap;font-weight:600;
 font-family:var(--serif);text-transform:none;letter-spacing:0}

/* What happened in the node you picked. */
#dmap .side{flex:none;width:23rem;border-left:1px solid var(--line);background:var(--surface);
 display:flex;flex-direction:column;min-height:0}
#dmap .side .side-in{overflow:auto;padding:var(--s4) var(--s5) var(--s5)}
#dmap .side h3{font:400 var(--t-title)/1.25 var(--serif);margin:0;color:var(--navy)}
#dmap .side .idline{font-family:var(--mono);font-size:var(--t-xs);color:var(--ink-3);margin:.15rem 0 var(--s3)}
#dmap .side .ev{border-left:2px solid var(--line);padding:.35rem 0 .35rem .7rem;margin-bottom:.35rem}
#dmap .side .ev.bad{border-left-color:var(--bad)}
#dmap .side .ev .t{font-family:var(--mono);font-size:var(--t-label);color:var(--ink-3)}
#dmap .side .ev .m{display:block;font-size:var(--t-xs);color:var(--ink-3);line-height:1.45;margin-top:.1rem}
#dmap .side .when{float:right;font-size:var(--t-label);color:var(--ink-3);
 font-variant-numeric:tabular-nums}
@media (max-width:1100px){
 #dmap .side{display:flex;position:absolute;inset:auto 0 0 0;width:auto;max-height:48%;
  border-left:0;border-top:1px solid var(--line);box-shadow:var(--shadow-lift)}
 #dmap .plate{display:none}
 #dmap .map-top{flex-wrap:wrap}
 #dmap .map-tools{margin-left:0}
}
"""

MAP_HTML = """
<div id="dmap" aria-hidden="true" role="dialog" aria-modal="true" tabindex="-1"
 aria-label="The whole design, painted with one run" aria-describedby="dmap-why">
 <p class="said" id="dmap-said" role="status" aria-live="polite"></p>
 <div class="map-top">
  <div class="head">
   <h2><span id="dmap-title">The whole design</span><span class="of" id="dmap-count"></span></h2>
   <p class="why" id="dmap-why">Every part of the system, with this run's way through it.</p>
  </div>
  <div class="map-tools">
   <input class="find" id="dmap-find" type="search" placeholder="Find a part of the system" aria-label="Find a part of the system by name or id">
   <span class="found" id="dmap-found" role="status" aria-live="polite" aria-atomic="true"></span>
   <span class="seg" role="group" aria-label="Walk the places this run went, in order">
    <button data-act="mapStep" data-by="-1" title="The one before (p)" aria-label="The place before this one">&lsaquo;</button>
    <span class="at" id="dmap-at">in order</span>
    <button data-act="mapStep" data-by="1" title="The next one (n)" aria-label="The next place this run went">&rsaquo;</button>
   </span>
   <span class="zoom">
    <button data-act="mapZoom" data-by="-1" title="Zoom out" aria-label="Zoom out">&minus;</button>
    <span class="lvl" id="dmap-lvl">100%</span>
    <button data-act="mapZoom" data-by="1" title="Zoom in" aria-label="Zoom in">+</button>
   </span>
   <button data-act="mapStop" title="The part this run stopped at">Go to the stop</button>
   <button data-act="mapFocus" title="Zoom to the part of the system this run went through">Where it ran</button>
   <button data-act="mapFit" title="The whole system at once">Show everything</button>
   <span class="sep" aria-hidden="true"></span>
   <button class="ghost" data-act="mapClose" title="Close this view (Esc)">Close</button>
  </div>
 </div>
 <div class="map-body">
  <div class="stage" id="dmap-stage">
   <div class="pan" id="dmap-pan"><svg id="dmap-edges"></svg><svg id="dmap-path"></svg></div>
   <div class="rail" id="dmap-rail" aria-hidden="true"></div>
   <div class="plate">
    <span class="map-legend" role="group" aria-label="Show or hide by what happened">
     <button data-act="mapFilter" data-state="passed" aria-pressed="true"><i class="mn passed"></i>passed</button>
     <button data-act="mapFilter" data-state="failed" aria-pressed="true"><i class="mn failed"></i>failed</button>
     <button data-act="mapFilter" data-state="active" aria-pressed="true"><i class="mn active"></i>running</button>
     <button data-act="mapFilter" data-state="used" aria-pressed="true"><i class="mn used"></i>touched</button>
     <button data-act="mapFilter" data-state="blocked" aria-pressed="true"><i class="mn blocked"></i>never got to</button>
     <button data-act="mapFilter" data-state="notreached" aria-pressed="true"><i class="mn notreached"></i>not used here</button>
    </span>
    <span class="hidden-note" id="dmap-drawn"></span>
    <span class="hidden-note" id="dmap-hidden"></span>
    <!-- Every key the map handles, because a shortcut nobody can find is one nobody uses:
         `+` and `-` were bound and undocumented, and "0 fits" reads as a count of
         something rather than as a key and a verb. A test holds this line to the handler. -->
    <span class="keys">n and p walk the run &middot; / finds &middot; + and &minus; zoom
     &middot; 0 fits it to the window &middot; Esc closes</span>
   </div>
  </div>
  <aside class="side" id="dmap-side"><div class="side-in" id="dmap-side-in"></div></aside>
 </div>
</div>
"""

MAP_JS = """
/* The whole design, painted with what one run did.

   Positions come from the blueprint through /api/graph, so this draws the design of record
   rather than a second layout of the same graph. What a run did comes from the trace it
   already has, and what happened inside a node is the events it recorded against it. */
/* One binding per line: the checkpoint reads the first name on a declaration, so a
   second name on the same line is a collision with the page's script that no test sees -
   and a duplicate `let` across two classic scripts is a SyntaxError that silently deletes
   this entire file from the page. */
let MAP_RUN = null;
let MAP_STATES = {};
let MAP_EVENTS = {};
let MAP_PICKED = null;
let MAP_TRACE = null;
let MAP_K = 1;
let MAP_X = 0;
let MAP_Y = 0;
let MAP_BUILT = false;
let MAP_CAME_FROM = null;
let MAP_OPENING = 0;
let MAP_RECT = null;
let MAP_URL_TIMER = null;
let MAP_NODE_H = 52;
let MAP_UNREAD = false;
let MAP_RESIZE = null;
let MAP_HOPS = [];
let MAP_RUN_DETAIL = null;
/* The order the run touched things in, and what each node is joined to. */
let MAP_ORDER = [];
let MAP_SEQ = {};
const MAP_IN = {};
const MAP_OUT = {};
const MAP_LABEL = {};
const MAP_NAME = {};
const MAP_PAD = 120;

async function openMap(runId, nodeId) {
  // A second open while the first is still fetching would otherwise capture the find box
  // as the element to hand focus back to, and paint twice.
  const mine = ++MAP_OPENING;
  const already = $('dmap').classList.contains('on');
  let g;
  try {
    g = await loadGraph();
  } catch (err) {
    return say('Could not read the blueprint from this server, so the map cannot be drawn.', 'bad');
  }
  if (mine !== MAP_OPENING) return;
  if (!g.nodes.length || g.nodes[0].x === null || g.nodes[0].x === undefined) {
    // Said to an analyst at seven in the evening, not to whoever built the exporter.
    return say('This picture is not available on this build. What the run did is still on '
      + "the run's own page, under Run trace.", 'bad');
  }
  MAP_RUN = runId;
  // The run's own trace, always. Reusing the page's saved one request and drew a run
  // that had passed through twenty-one nodes as one that had reached four, because the
  // stream paints as it goes and the map opened on a half-built snapshot.
  let unread = false;
  const trace = await get(`/api/runs/${encodeURIComponent(runId)}/trace`)
    .catch(() => { unread = true; return {nodes: {}}; });
  if (mine !== MAP_OPENING) return;
  MAP_TRACE = trace;
  MAP_STATES = trace.nodes || {};
  MAP_EVENTS = {};
  const events = await get(`/api/runs/${encodeURIComponent(runId)}/events`)
    .catch(() => { unread = true; return []; });
  if (mine !== MAP_OPENING) return;
  for (const e of events) {
    const at = String(e.node_id || '');
    if (at) (MAP_EVENTS[at] = MAP_EVENTS[at] || []).push(e);
  }
  // A run that could not be read is not a run that did nothing, and this is the view whose
  // whole purpose is not confusing those two. Say which one this is.
  MAP_UNREAD = unread;
  // The run's record, for what a person actually asks: what happened to it, how far it
  // got, how long it took and what it cost.
  MAP_RUN_DETAIL = await get(`/api/runs/${encodeURIComponent(runId)}`).catch(() => null);
  if (mine !== MAP_OPENING) return;
  // The order it went through them: first time each node was written against. A run is a
  // sequence and the drawing is not, so this is the only place the picture can say so.
  MAP_ORDER = [];
  const seen = new Set();
  for (const e of events) {
    const at = String(e.node_id || '');
    if (!at || seen.has(at)) continue;
    seen.add(at);
    if ((MAP_STATES[at] || 'notreached') !== 'notreached') MAP_ORDER.push(at);
  }
  MAP_SEQ = {};
  MAP_ORDER.forEach((id, i) => { MAP_SEQ[id] = i + 1; });
  if (!MAP_BUILT) buildMap(g);
  paintMap(trace);
  mapHeader(runId);
  if (!already) MAP_CAME_FROM = document.activeElement;
  $('dmap').classList.add('on');
  $('dmap').setAttribute('aria-hidden', 'false');
  // The page underneath is covered by an opaque overlay; leaving it reachable is how Tab
  // walks off into a run list nobody can see - and the masthead's links come first in the
  // document, so they are where it lands.
  mapBehind(true);
  MAP_RECT = null;
  history.replaceState(null, '', mapHash(runId, nodeId));
  document.addEventListener('keydown', mapKeys);
  const find = $('dmap-find');
  if (find) { find.value = ''; mapFind(); }
  // Not the find box: focusing an input turns off every shortcut the buttons advertise,
  // including the arrow keys that pan. The dialog itself takes the focus.
  $('dmap').focus();
  if (MAP_UNREAD) {
    say(`Could not read what ${runId} did. The design is drawn; what happened on it is not.`, 'bad');
  }
  // Not the whole canvas: the part this run actually went through, at a size its labels
  // can be read at. "Fit all" is the other question, and it is one button away.
  mapFocus();
  // On the stop, when there is one and the link did not ask for somewhere else: "where did
  // it stop" is the reason this view gets opened.
  const stopped = Object.keys(MAP_STATES).find(id => MAP_STATES[id] === 'failed' && $('mn-' + id));
  pickNode(nodeId && $('mn-' + nodeId) ? nodeId : (stopped || null));
}

/* The machine's event names, in the words the tool already uses elsewhere. Anything not
   named here falls back to its own type with the dots opened out, so a new event is
   readable on the day it is added rather than on the day somebody remembers this table. */
const MAP_EVENT_SAYS = {
  'run.launched': 'the run started',
  'intake.read': 'read the files that came in',
  'model.called': 'asked the model',
  'step.started': 'started a step',
  'step.completed': 'finished a step',
  'step.quarantined': 'stopped on a step that will not come right by retrying',
  'step.satisfied': 'the step was already done',
  'lock.released': 'released the engagement lock',
  'worker.finished': 'the worker finished',
  'hitl.pass.paused': 'paused for a person to look at it',
  'precedent.writeback.refused': 'refused to learn from this - no human decision behind it',
};

function mapSays(type) {
  return MAP_EVENT_SAYS[type] || String(type).replace(/[._]/g, ' ');
}

/* How long something took, in the words a person says it in. */
/* From the first thing recorded against a node to the last. The panel printed both and
   never subtracted them. */
function mapTook(events) {
  if (events.length < 2) return '';
  const first = Date.parse(events[0].ts), last = Date.parse(events[events.length - 1].ts);
  if (!first || !last || last < first) return '';
  return mapFor((last - first) / 1000) || 'under a second';
}

function mapFor(seconds) {
  if (!seconds && seconds !== 0) return '';
  if (seconds < 90) return `${Math.round(seconds * 10) / 10}s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds / 360) / 10} hours`;
}

/* The masthead of the view: whose run, what happened to it, and how far it got - against a
   denominator that means something. "20 of 118 touched" was read as ten per cent complete,
   and the 118 includes every connector and bench no run ever goes near. */
function mapHeader(runId) {
  const run = RUNS.find(r => r.run_id === runId) || {};
  const detail = MAP_RUN_DETAIL || {};
  const steps = detail.steps || [];
  const done = steps.filter(st => st.status === 'completed').length;
  $('dmap-title').textContent = run.client || detail.engagement_id || runId;

  const count = $('dmap-count');
  count.textContent = steps.length ? `${done} of ${steps.length} steps done` : '';

  const spend = detail.spend || {};
  const when = String(detail.started_at || '').slice(11, 16);
  const parts = [runId];
  if (STATE_SAYS[detail.state]) parts.push(STATE_SAYS[detail.state]);
  else if (detail.state) parts.push(detail.state);
  if (when) parts.push(`started ${when}`);
  if (spend.active_seconds) parts.push(mapFor(spend.active_seconds) + ' of work');
  if (spend.usd !== undefined) {
    parts.push(usd(spend.usd) + (detail.budget_usd ? ' of ' + usd(detail.budget_usd) : ''));
  }
  $('dmap-why').textContent = parts.join(' \u00b7 ');
}

/* Everything the overlay covers, taken out of the tab order and out of the accessibility
   tree while it is covered. `aria-modal` alone only promises this; `inert` does it. */
function mapBehind(off) {
  document.querySelectorAll('.top, .wrap').forEach(el => { el.inert = off; });
}

/* A link to a run's map, or to one node of it: what somebody pastes into a message when
   the question is "look at where this stopped". */
function mapHash(runId, nodeId) {
  return '#map=' + encodeURIComponent(runId) + (nodeId ? '/' + encodeURIComponent(nodeId) : '');
}

function closeMap() {
  $('dmap').classList.remove('on');
  $('dmap').setAttribute('aria-hidden', 'true');
  document.removeEventListener('keydown', mapKeys);
  mapBehind(false);
  // Back where it came from - but refresh() rewrites the run's buttons every five seconds,
  // so by the time anybody closes this, the element it was opened from is usually detached
  // and focusing it does nothing at all. Fall back to the control that exists now.
  const back = (MAP_CAME_FROM && MAP_CAME_FROM.isConnected) ? MAP_CAME_FROM
    : (document.querySelector('[data-act="map"]') || document.querySelector('#runs .r.on'));
  if (back && back.focus) back.focus();
  if (MAP_RUN) history.replaceState(null, '', '#' + encodeURIComponent(MAP_RUN));
}

function mapKeys(e) {
  // Tab first: the guard below turns the trap off while anything is typed into, and the
  // find box is exactly where a reader is when they press it.
  if (e.key === 'Tab') return mapTrap(e);
  const typing = e.target && e.target.closest('input,textarea,select,[contenteditable="true"]');
  if (e.key === 'Escape') return typing ? undefined : closeMap();
  if (typing) return;
  // Ctrl+P is print and Ctrl+N is a new window. A single-letter shortcut that does not
  // check for a modifier takes both of them away from the browser.
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  // The side panel scrolls; the arrow keys belong to it while the reader is in it.
  if (e.target && e.target.closest('#dmap-side')) return;
  const step = e.shiftKey ? 240 : 80;
  const moves = {ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step]};
  if (moves[e.key]) { e.preventDefault(); MAP_X += moves[e.key][0]; MAP_Y += moves[e.key][1]; mapApply(); }
  if (e.key === '+' || e.key === '=') { e.preventDefault(); mapZoom(1); }
  if (e.key === '-') { e.preventDefault(); mapZoom(-1); }
  if (e.key === '0') { e.preventDefault(); mapFit(); }
  if (e.key === 'n' || e.key === ']') { e.preventDefault(); mapStep(1); }
  if (e.key === 'p' || e.key === '[') { e.preventDefault(); mapStep(-1); }
  if (e.key === '/') { e.preventDefault(); $('dmap-find').focus(); }
}

/* The map covers the screen, so Tab belongs in it: tabbing out lands on a page nobody can
   see, which is worse than having no focus at all. */
function mapTrap(e) {
  const box = $('dmap');
  const stops = [...box.querySelectorAll('button,input,[tabindex]')]
    .filter(el => el.tabIndex >= 0 && !el.disabled && el.offsetParent !== null);
  if (!stops.length) return;
  const at = stops.indexOf(document.activeElement);
  e.preventDefault();
  // Focus outside the dialog - after a pan, or on a deep link - re-enters it rather than
  // being left where the browser would take it.
  if (at === -1) return (e.shiftKey ? stops[stops.length - 1] : stops[0]).focus();
  stops[(at + (e.shiftKey ? -1 : 1) + stops.length) % stops.length].focus();
}

/* Through the run, in the order it happened. The whole point of a sequence is being able
   to walk it. */
function mapStep(by) {
  if (!MAP_ORDER.length) return say('This run went nowhere there is to walk through.', 'warn');
  // Whatever the legend is hiding is not somewhere to step to.
  const walk = MAP_ORDER.filter(id => {
    const el = $('mn-' + id);
    return !el || el.offsetParent !== null;
  });
  if (!walk.length) return say('Every step of this run is hidden by the filters.', 'warn');
  const at = MAP_PICKED ? walk.indexOf(MAP_PICKED) : -1;
  const next = at === -1 ? (by > 0 ? 0 : walk.length - 1)
    : (at + by + walk.length) % walk.length;
  pickNode(walk[next]);
}

/* One of 118 nodes, by name, id or group. */
function mapFind() {
  const q = ($('dmap-find').value || '').trim().toLowerCase();
  let hits = 0;
  document.querySelectorAll('#dmap-pan .mn').forEach(el => {
    const hit = Boolean(q) && el.dataset.search.includes(q) && el.offsetParent !== null;
    el.classList.toggle('hit', hit);
    if (hit) hits++;
  });
  $('dmap-found').textContent = q ? (hits ? hits + ' found' : 'none') : '';
  return hits;
}

function mapFindEnter() {
  const first = document.querySelector('#dmap-pan .mn.hit');
  if (first) pickNode(first.dataset.node);
}

/* The sheet's size, written by buildMap from the blueprint's own extent. It starts at
   nothing rather than at a hand-copied 2600x2900, which was a near-duplicate of derived
   data - the real canvas is 2598x2868 - and would have been silently wrong the moment a
   node moved in the blueprint. Nothing can reach it before buildMap fills it.
   Declared above its first use, so a future top-level call cannot hit the dead zone. */
const MAP_SIZE = {w: 0, h: 0};

/* Built once: 118 nodes and 240 edges do not change between runs - only their colours do.
   Note every query below says `#dmap-pan .mn` rather than `#dmap .mn`: the legend's
   swatches are `.mn` elements too, deliberately, so that the key cannot drift from the
   thing it is a key to. They are not nodes of the design. */
function buildMap(g) {
  const pan = $('dmap-pan'), svg = $('dmap-edges');
  /* One marker for all 240 lines: `context-stroke` makes it take the colour of the path it
     ends, so recolouring a line in paintMap recolours its head for nothing. userSpaceOnUse
     keeps the head a constant size instead of growing with the stroke width. */
  svg.innerHTML = `<defs><marker id="dmap-head" viewBox="0 0 8 6" refX="7.4" refY="3"
    markerWidth="7" markerHeight="5" orient="auto" markerUnits="userSpaceOnUse">
    <path d="M0,.3 L8,3 L0,5.7 Z" fill="context-stroke"></path></marker></defs>`;
  const at = {};
  g.nodes.forEach(n => { at[n.id] = n; });
  const width = Math.max(...g.nodes.map(n => n.x)) + 178 + MAP_PAD;
  const height = Math.max(...g.nodes.map(n => n.y)) + 90 + MAP_PAD;
  pan.style.width = width + 'px';
  pan.style.height = height + 'px';
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  MAP_SIZE.w = width;
  MAP_SIZE.h = height;

  const layout = g.layout || {};
  // One margin for the sheet, so the rules and the labels line up against the same edge.
  const EDGE = 48;
  (layout.bands || []).forEach(b => {
    const rule = document.createElement('div');
    rule.className = 'band' + (b.privacy ? ' priv' : '');
    rule.style.cssText = `left:${EDGE}px;top:${b.y}px;width:${width - EDGE * 2}px`;
    pan.appendChild(rule);
    const label = document.createElement('div');
    label.className = 'band-t' + (b.privacy ? ' priv' : '');
    label.dataset.y = b.y;
    label.title = b.label;
    label.textContent = b.label;
    $('dmap-rail').appendChild(label);
  });
  (layout.columns || []).forEach(c => {
    const label = document.createElement('div');
    label.className = 'col-t';
    label.style.cssText = `left:${c.x}px;top:${c.y + 6}px`;
    label.textContent = c.label;
    pan.appendChild(label);
  });

  /* The boxes go down first and one of them is measured, because an edge has to be drawn
     to the box that is there rather than to a number written beside it. The SVG is already
     in the DOM above them, so the lines still pass behind. */
  g.nodes.forEach(n => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'mn';
    el.id = 'mn-' + n.id;
    el.style.cssText = `left:${n.x}px;top:${n.y}px`;
    el.dataset.act = 'mapPick';
    el.dataset.node = n.id;
    el.title = n.plain || n.label;
    el.dataset.search = `${n.label} ${n.id} ${n.group || ''}`.toLowerCase();
    el.innerHTML = `<span class="ord" aria-hidden="true"></span>`
      + `<span class="nm">${esc(n.label)}</span><span class="id">${esc(n.id)}</span>`;
    pan.appendChild(el);
    MAP_NAME[n.id] = n.label;
  });
  const first = g.nodes.length ? $('mn-' + g.nodes[0].id) : null;
  MAP_NODE_H = (first && Math.round(first.getBoundingClientRect().height)) || 52;

  /* An edge leaves the side of a box when the two are mostly apart, and the top or bottom
     when one is mostly above the other - the blueprint's own rule, so the picture reads
     the same way in both places. */
  const NH = MAP_NODE_H;
  (g.edges || []).forEach((e, i) => {
    const a = at[e.from], b = at[e.to];
    if (!a || !b) return;
    const ax = a.x + 89, ay = a.y + NH / 2, bx = b.x + 89, by = b.y + NH / 2;
    const dx = bx - ax, dy = by - ay;
    let d;
    if (Math.abs(dx) > Math.abs(dy) * 1.15 || Math.abs(dx) > 430) {
      const x1 = dx > 0 ? a.x + 178 : a.x, x2 = dx > 0 ? b.x : b.x + 178, m = (x1 + x2) / 2;
      d = `M${x1},${ay} C${m},${ay} ${m},${by} ${x2},${by}`;
    } else if (dy > 0) {
      const y1 = a.y + NH, y2 = b.y, m = (y1 + y2) / 2;
      d = `M${ax},${y1} C${ax},${m} ${bx},${m} ${bx},${y2}`;
    } else {
      const y1 = a.y, y2 = b.y + NH, m = (y1 + y2) / 2;
      d = `M${ax},${y1} C${ax},${m} ${bx},${m} ${bx},${y2}`;
    }
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-linecap', 'round');
    path.id = 'me-' + i;
    path.dataset.from = e.from;
    path.dataset.to = e.to;
    path.dataset.kind = e.kind || 'flow';
    path.setAttribute('marker-end', 'url(#dmap-head)');
    svg.appendChild(path);
    (MAP_OUT[e.from] = MAP_OUT[e.from] || []).push(e.to);
    (MAP_IN[e.to] = MAP_IN[e.to] || []).push(e.from);
    MAP_LABEL[e.from + '>' + e.to] = e.label || '';
  });

  MAP_BUILT = true;
}


const MAP_ALL_STATES = ['passed', 'failed', 'active', 'used', 'notreached', 'pending', 'blocked'];
/* What each state is called, once, for the canvas label, the announcement and the panel. */
const MAP_SAYS = {passed: 'done', failed: 'failed', active: 'running now', used: 'ran',
  blocked: 'never got to - it stopped before here',
  notreached: 'not used on this run', pending: 'still to come'};

/* The route, hop by hop, from the order the run recorded. A hop that is a blueprint edge
   is left to that edge - the geometry already says it, and drawing a chord over a line
   that is already there is just a thicker line. A hop that is not gets a trail, because
   the alternative is to leave the biggest thing the run did undrawn. */
function drawPath() {
  const svg = $('dmap-path');
  svg.setAttribute('width', MAP_SIZE.w);
  svg.setAttribute('height', MAP_SIZE.h);
  svg.innerHTML = '';
  MAP_HOPS = [];
  for (let i = 0; i < MAP_ORDER.length - 1; i++) {
    const from = MAP_ORDER[i], to = MAP_ORDER[i + 1];
    const a = $('mn-' + from), b = $('mn-' + to);
    // A hop through a name the design has no box for cannot be drawn; the panel names it.
    if (!a || !b) continue;
    const known = (MAP_OUT[from] || []).includes(to);
    MAP_HOPS.push({from, to, known});
    if (known) continue;
    const ax = parseFloat(a.style.left) + 89, ay = parseFloat(a.style.top) + MAP_NODE_H / 2;
    const bx = parseFloat(b.style.left) + 89, by = parseFloat(b.style.top) + MAP_NODE_H / 2;
    // Bowed away from the straight line, so a hop is never mistaken for an edge.
    const mx = (ax + bx) / 2 + (by - ay) * .12, my = (ay + by) / 2 - (bx - ax) * .12;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${ax},${ay} Q${mx},${my} ${bx},${by}`);
    path.setAttribute('class', 'off');
    svg.appendChild(path);
  }
}

/* Everything downstream of where the run stopped that it never reached. Breadth-first
   over the blueprint's own edges - the answer to "what would have come next" is in the
   drawing already, it was just never asked. */
function blockedBy(states) {
  const stopped = Object.keys(states).filter(id => states[id] === 'failed');
  if (!stopped.length) return new Set();
  const out = new Set();
  const queue = [...stopped];
  while (queue.length) {
    for (const next of MAP_OUT[queue.shift()] || []) {
      const state = states[next] || 'notreached';
      if (out.has(next) || (state !== 'notreached' && state !== 'pending')) continue;
      out.add(next);
      queue.push(next);
    }
  }
  return out;
}

/* The colours, from the trace this run recorded. Everything else stays outlined. */
function paintMap(trace) {
  const states = (trace && trace.nodes) || {};
  const blocked = blockedBy(states);
  let touched = 0;
  const says = MAP_SAYS;
  document.querySelectorAll('#dmap-pan .mn').forEach(el => {
    const id = el.id.slice(3);
    const state = states[id] || (blocked.has(id) ? 'blocked' : 'notreached');
    const went = state !== 'notreached' && state !== 'pending';
    for (const was of MAP_ALL_STATES) el.classList.remove(was);
    el.classList.add(state);
    el.classList.toggle('on', MAP_PICKED === id);
    if (MAP_SEQ[id]) el.dataset.ord = MAP_SEQ[id]; else delete el.dataset.ord;
    el.querySelector('.ord').textContent = MAP_SEQ[id] || '';
    // A hundred and eighteen tab stops is not navigation. The keyboard goes to what the
    // run touched; the rest are reachable by the find box.
    el.tabIndex = went ? 0 : -1;
    el.setAttribute('aria-label',
      `${MAP_NAME[id] || id}, ${says[state] || state}` + (MAP_SEQ[id] ? `, step ${MAP_SEQ[id]}` : ''));
    if (went) touched++;
  });
  // Crossed, not merely adjacent. Deciding by both ends having been touched lit thirteen
  // edges on a twenty-node run, eight of which the run never went along.
  const crossed = new Set();
  for (let i = 0; i < MAP_ORDER.length - 1; i++) {
    crossed.add(MAP_ORDER[i] + '>' + MAP_ORDER[i + 1]);
  }
  document.querySelectorAll('#dmap-edges path').forEach(p => {
    const a = states[p.dataset.from] || 'notreached', b = states[p.dataset.to] || 'notreached';
    for (const was of MAP_ALL_STATES) p.classList.remove('f-' + was, 't-' + was);
    p.classList.add('f-' + a, 't-' + b);
    const live = crossed.has(p.dataset.from + '>' + p.dataset.to);
    const failed = live && (a === 'failed' || b === 'failed');
    p.setAttribute('stroke', failed ? 'var(--bad)' : live ? 'var(--accent)' : 'var(--line)');
    // Weight belongs to the edge's kind, which is fixed; only presence and opacity say
    // what this run did. Writing a width here used to flatten the grammar back out.
    p.setAttribute('stroke-opacity', live ? .8 : .3);
    p.classList.toggle('live', Boolean(live));
  });
  drawPath();
  const drawn = document.querySelectorAll('#dmap-pan .mn').length;
  const off = Object.entries(states).filter(([id, st]) =>
    st !== 'notreached' && st !== 'pending' && !$('mn-' + id)).length;
  const note = $('dmap-drawn');
  if (note) {
    note.textContent = `${touched} of ${drawn} parts used`
      + (off ? ` \u00b7 ${off} not in this drawing` : '');
  }
}

/* What happened in one node: the state the trace gave it, what the blueprint says it is
   for, and every event this run recorded against it. */
async function pickNode(id) {
  MAP_PICKED = id;
  const near = new Set([...(MAP_IN[id] || []), ...(MAP_OUT[id] || [])]);
  document.querySelectorAll('#dmap-pan .mn').forEach(el => {
    el.classList.toggle('on', el.id === 'mn-' + id);
    el.classList.toggle('near', near.has(el.id.slice(3)));
  });
  // The hairball is 240 edges at one weight. Picking a node draws the ones it is on and
  // lets the rest fall back, which is the only way to read what feeds what.
  const drawn = Boolean(id) && Boolean($('mn-' + id));
  $('dmap').classList.toggle('focused', drawn);
  if (id && !drawn) {
    say(`${id} is a name this run recorded work against that the design has no box for.`, 'warn');
  }
  document.querySelectorAll('#dmap-edges path').forEach(path => {
    path.classList.toggle('on', Boolean(id) && (path.dataset.from === id || path.dataset.to === id));
  });
  const said = $('dmap-said');
  if (said && id) {
    said.textContent = `${MAP_NAME[id] || id}, ${MAP_SAYS[MAP_STATES[id]] || 'not used on this run'}`
      + (MAP_SEQ[id] ? `, ${MAP_SEQ[id]} of ${MAP_ORDER.length}` : '');
  } else if (said) {
    // Clicking the paper means "the whole run again", and that was never announced.
    said.textContent = MAP_ORDER.length
      ? `Nothing picked. The whole run, ${MAP_ORDER.length} places.` : 'Nothing picked.';
  }
  const at = $('dmap-at');
  // One shape, so the slot does not change grammar under the reader as it changes value.
  if (at) at.textContent = MAP_ORDER.length
    ? `${id && MAP_SEQ[id] ? MAP_SEQ[id] : '\u2013'} of ${MAP_ORDER.length}` : 'in order';
  mapLink(id);
  const chosen = id ? $('mn-' + id) : null;
  if (chosen) {
    // Bring it under the eye rather than leaving the reader to find it on a canvas the
    // size of a wall.
    const stage = mapStage();
    const x = parseFloat(chosen.style.left), y = parseFloat(chosen.style.top);
    // Below 1100px the side panel is a sheet over the bottom 55% of this same stage, so
    // the middle of the stage is behind it.
    const side = $('dmap-side');
    const over = side && getComputedStyle(side).position === 'absolute'
      ? side.getBoundingClientRect().height : 0;
    MAP_X = stage.width / 2 - (x + 89) * MAP_K;
    MAP_Y = (stage.height - over) / 2 - (y + MAP_NODE_H / 2) * MAP_K;
    mapGlide();
    mapApply();
  }
  $('dmap').classList.toggle('picked', Boolean(id));
  const box = $('dmap-side-in');
  if (!id) {
    const g0 = await loadGraph();
    const named = {};
    (g0.nodes || []).forEach(n => { named[n.id] = n.label; });
    const onCanvas = new Set((g0.nodes || []).map(n => n.id));
    // In the order it happened, not in the order a dictionary put them: the first
    // question of a run is what it did, then, and then.
    const ordered = MAP_ORDER.map(nodeId => [nodeId, MAP_STATES[nodeId]]);
    const rest = Object.entries(MAP_STATES)
      .filter(([nodeId, state]) => state !== 'notreached' && state !== 'pending' && !MAP_SEQ[nodeId]);
    // The numbers run across everything the run recorded, so a number missing from the
    // list below is one of the names further down, not a hole.
    const reached = [...ordered, ...rest];
    const went = reached.filter(([nodeId]) => onCanvas.has(nodeId));
    // Recorded against a node the design of record does not have. Not dropped: dropping it
    // is how a drawing and a system come to disagree without anybody noticing.
    const stray = reached.filter(([nodeId]) => !onCanvas.has(nodeId));
    box.innerHTML = mapVerdict() + (went.length
      ? `<div class="section-label">Where it went, in order</div>
         <p class="idline" style="margin-top:0">${went.length} places &middot; pick one for what happened there</p>`
        + went.map(([nodeId, state]) => `<div class="r pick" data-act="mapPick" data-node="${esc(nodeId)}" role="button" tabindex="0">
            <span class="lbl"><b>${MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. ' : ''}${esc(named[nodeId] || nodeId)}</b><span class="sub" style="display:block">${esc(nodeId)}${
              (MAP_EVENTS[nodeId] || []).length ? ' &middot; ' + esc(String(MAP_EVENTS[nodeId][0].ts).slice(11, 19)) : ''}${
              mapTook(MAP_EVENTS[nodeId] || []) ? ' &middot; ' + esc(mapTook(MAP_EVENTS[nodeId])) : ''}</span></span>
            <span class="pill ${state === 'passed' ? 'good' : state === 'failed' ? 'bad' : state === 'active' ? 'accent' : ''}"><i class="dot" aria-hidden="true"></i>${esc(state)}</span>
           </div>`).join('')
      : (MAP_UNREAD
         ? `<div class="empty"><b>Could not read this run</b>The design is drawn, but what
            happened on it could not be fetched. Reopen the map to try again.</div>`
         : `<div class="empty"><b>Nothing ran</b>This run used no part of the system - it was
            refused or replaced before it started. Every part is still drawn, in outline.</div>`));
    if (stray.length) {
      box.innerHTML += `<div class="section-label">Recorded, but not in the drawing</div>
        <p class="note" style="margin-top:0">This run recorded work under
         ${plural(stray.length, 'name', 'names')} the design of record has no part for.
         That is a difference between the system and its blueprint, not a gap in the drawing.</p>`
        + stray.map(([nodeId, state]) => `<div class="r">
            <span class="lbl"><b class="mono">${MAP_SEQ[nodeId] ? esc(MAP_SEQ[nodeId]) + '. ' : ''}${esc(nodeId)}</b></span>
            <span class="pill ${state === 'failed' ? 'bad' : ''}"><i class="dot" aria-hidden="true"></i>${esc(state)}</span>
           </div>`).join('');
    }
    return;
  }
  const g = await loadGraph();
  const node = (g.nodes || []).find(n => n.id === id) || {id, label: id};
  const state = MAP_STATES[id] || 'notreached';
  const says = {passed: 'done here', failed: 'failed here', active: 'running here now',
    used: 'ran here', blocked: 'never got here - the run stopped before it',
    notreached: 'not used on this run', pending: 'still to come'};
  const events = MAP_EVENTS[id] || [];
  const diagnostic = ((MAP_TRACE || {}).diagnostics || {})[id];
  box.innerHTML = `<h3>${esc(node.label)}</h3>
    <p class="idline">${esc(node.id)}${node.exec ? ' &middot; runs as ' + esc(node.exec) : ''}${
      node.group ? ' &middot; part of ' + esc(node.group) : ''}</p>
    <div class="r" style="border:0;padding:0 0 .6rem"><span class="pill ${
      state === 'passed' ? 'good' : state === 'failed' ? 'bad' : state === 'active' ? 'accent' : ''
    }"><i class="dot" aria-hidden="true"></i>${esc(says[state] || state)}</span></div>
    ${node.plain ? `<p class="note" style="margin-top:0">${esc(node.plain)}</p>` : ''}
    ${events.length ? `<p class="idline" style="margin:.4rem 0 0">${plural(events.length, 'event', 'events')}
      &middot; ${esc(String(events[0].ts).slice(11, 19))}${events.length > 1
        ? '&ndash;' + esc(String(events[events.length - 1].ts).slice(11, 19))
          + ' &middot; ' + esc(mapTook(events)) + ' here' : ''}${
        MAP_SEQ[id] ? ' &middot; ' + esc(MAP_SEQ[id]) + ' of ' + esc(MAP_ORDER.length) : ''}</p>` : ''}
    <div class="section-label">What it is joined to</div>
    <div class="chips">${
      (MAP_IN[id] || []).length
        ? (MAP_IN[id] || []).map(from => `<button data-act="mapPick" data-node="${esc(from)}"
            title="${esc(MAP_LABEL[from + '>' + id] || 'feeds this node')}">&larr; ${esc(MAP_NAME[from] || from)}</button>`).join('')
        : '<span class="none">nothing feeds this node</span>'}</div>
    <div class="chips">${
      (MAP_OUT[id] || []).length
        ? (MAP_OUT[id] || []).map(to => `<button data-act="mapPick" data-node="${esc(to)}"
            title="${esc(MAP_LABEL[id + '>' + to] || 'this node feeds it')}">&rarr; ${esc(MAP_NAME[to] || to)}</button>`).join('')
        : '<span class="none">this node feeds nothing</span>'}</div>
    ${diagnostic ? `<div class="diag"><div class="d-row"><span class="code">${esc(diagnostic.code || '')}</span>
      <span class="msg">${esc(diagnostic.message || diagnostic.detail || '')}</span></div></div>` : ''}
    <div class="section-label">What happened here</div>
    ${events.length ? events.map(e => `<div class="ev${String(e.type).endsWith('fail') ? ' bad' : ''}">
        <span class="when">${esc((e.ts || '').slice(11, 19))}</span>
        <span class="t" title="${esc(e.type)}">${esc(mapSays(e.type))}</span>
        ${e.message ? `<span class="m">${esc(e.message)}</span>` : ''}</div>`).join('')
      : `<p class="note" style="margin-top:0">This run recorded nothing against this node.</p>`}`;
}

/* The address bar follows the selection, but at most four times a second: a held key
   would otherwise exhaust the browser's budget for rewriting it, and a browser that
   answers by throwing would abort this function before the panel is built. */
function mapLink(id) {
  if (!MAP_RUN) return;
  clearTimeout(MAP_URL_TIMER);
  MAP_URL_TIMER = setTimeout(() => {
    try { history.replaceState(null, '', mapHash(MAP_RUN, id)); } catch (err) { /* rate-limited */ }
  }, 250);
}

/* Moving from one step to the next is a movement; dragging is not. The class is put on
   for the length of one transition and taken off, so a drag is never animated - and because
   it is a CSS transition, the global reduced-motion rule turns it off without this file
   knowing anything about it. */
let MAP_GLIDE = null;
function mapGlide() {
  const pan = $('dmap-pan');
  pan.classList.add('gliding');
  clearTimeout(MAP_GLIDE);
  MAP_GLIDE = setTimeout(() => pan.classList.remove('gliding'), 380);
}

function mapStage() {
  return MAP_RECT || (MAP_RECT = $('dmap-stage').getBoundingClientRect());
}

/* What happened to this run, in six lines, before any node is picked.

   The words are the console's own - STATE_SAYS and STATE_TONE - rather than a second
   vocabulary invented here, so a change to one changes both. */
function mapVerdict() {
  const detail = MAP_RUN_DETAIL;
  if (!detail) return '';
  const steps = detail.steps || [];
  const done = steps.filter(st => st.status === 'completed').length;
  const stopped = Object.keys(MAP_STATES).filter(id => MAP_STATES[id] === 'failed');
  const where = stopped.length ? (MAP_NAME[stopped[0]] || stopped[0]) : '';
  const diagnostics = (MAP_TRACE || {}).diagnostics || {};
  const why = stopped.length ? diagnostics[stopped[0]] : null;
  const blocked = document.querySelectorAll('#dmap-pan .mn.blocked').length;
  const spend = detail.spend || {};

  // What to do next, and the button that does it. Both are the console's own actions.
  const next = {
    quarantined: ['Retrying on its own will not fix this. Fix the cause, then resume - it '
      + 'picks up from here rather than starting over.', 'resume', 'Resume this run'],
    waiting: ['This run is waiting on a person. Answer the open review items and it carries '
      + 'on by itself.', '', ''],
    blocked: ['A criterion was not met, so nothing was released.', '', ''],
    halted: ['This run ended without delivering. Nothing partial left the system.', '', ''],
  }[detail.state];

  return `<h3>${esc(STATE_SAYS[detail.state] || detail.state || 'this run')}</h3>
    <p class="idline">${esc(detail.engagement_id || '')} &middot; ${esc(MAP_RUN)}</p>
    <div class="r" style="border:0;padding:0 0 .5rem"><span class="pill ${
      STATE_TONE[detail.state] ?? ''}"><i class="dot" aria-hidden="true"></i>${esc(detail.state || '')}</span></div>
    ${where ? `<p class="note" style="margin-top:0">It stopped at
      <b><a href="#" data-act="mapPick" data-node="${esc(stopped[0])}">${esc(where)}</a></b>${
        why ? `. <span class="mono">${esc(why.code || '')}</span> ${esc(why.message || why.detail || '')}` : '.'}</p>` : ''}
    <dl class="kv">
      ${steps.length ? `<dt>Got through</dt><dd>${done} of ${steps.length} steps it planned</dd>` : ''}
      ${blocked ? `<dt>Never got to</dt><dd>${plural(blocked, 'part', 'parts')} downstream of the stop</dd>` : ''}
      ${spend.active_seconds ? `<dt>Time</dt><dd>${esc(mapFor(spend.active_seconds))} of work</dd>` : ''}
      ${spend.usd !== undefined ? `<dt>Cost</dt><dd>${esc(usd(spend.usd))}${
        detail.budget_usd ? ` <span class="sub">of ${esc(usd(detail.budget_usd))}</span>` : ''}</dd>` : ''}
    </dl>
    ${next ? `<p class="note">${esc(next[0])}</p>` : ''}
    ${next && next[1] ? `<div class="acts"><button class="primary" data-act="runAction"
      data-run="${esc(MAP_RUN)}" data-do="${esc(next[1])}">${esc(next[2])}</button>
      <button data-act="mapCopy">Copy a link to this</button></div>`
      : `<div class="acts"><button data-act="mapCopy">Copy a link to this</button></div>`}`;
}

/* Pan, zoom, fit. */
/* Where the sheet is allowed to be. When it is smaller than the frame it is centred in
   it; when it is larger, a quarter of the frame is the most ground that may show on any
   one side - so the drawing can always be got back to without a button. */
function mapClamp() {
  const stage = mapStage();
  const w = MAP_SIZE.w * MAP_K, h = MAP_SIZE.h * MAP_K;
  const slack = {x: stage.width * .25, y: stage.height * .25};
  MAP_X = w <= stage.width ? (stage.width - w) / 2
    : Math.min(slack.x, Math.max(stage.width - w - slack.x, MAP_X));
  MAP_Y = h <= stage.height ? (stage.height - h) / 2
    : Math.min(slack.y, Math.max(stage.height - h - slack.y, MAP_Y));
}

function mapApply() {
  mapClamp();
  $('dmap-pan').style.transform = `translate(${MAP_X}px,${MAP_Y}px) scale(${MAP_K})`;
  // The rail follows the drawing down the page and never across it.
  document.querySelectorAll('#dmap-rail .band-t').forEach(el => {
    el.style.top = (Number(el.dataset.y) * MAP_K + MAP_Y) + 'px';
  });
  const level = Math.round(MAP_K * 100) + '%';
  const lvl = $('dmap-lvl');
  if (lvl.textContent !== level) lvl.textContent = level;
  $('dmap').classList.toggle('far', MAP_K < .52);
}

function mapZoomTo(to, at) {
  const stage = mapStage();
  const cx = at ? at.x - stage.left : stage.width / 2;
  const cy = at ? at.y - stage.top : stage.height / 2;
  const next = Math.min(2.4, Math.max(.12, to));
  // Keep whatever is under the pointer (or the middle) where it is while the scale changes.
  MAP_X = cx - (cx - MAP_X) * (next / MAP_K);
  MAP_Y = cy - (cy - MAP_Y) * (next / MAP_K);
  MAP_K = next;
  mapApply();
}

/* One notch, for the buttons and the keys. */
function mapZoom(by, at) {
  mapZoomTo(MAP_K * (by > 0 ? 1.22 : 1 / 1.22), at);
}

/* Where the run ran, at a size its own marks survive.

   A run's bounding box is about 72% by 82% of the wall, so fitting it whole put the view
   at .31 - below the .52 where the labels go and the borders turn sub-pixel. Legibility
   wins: the view opens no smaller than FLOOR and centres on the run, and the parts that
   fall outside the window are reached by stepping, which is what the step control is for. */
const MAP_FLOOR = .62;

function mapFocus() {
  const touched = [];
  document.querySelectorAll('#dmap-pan .mn').forEach(el => {
    const state = MAP_STATES[el.id.slice(3)];
    if (state && state !== 'notreached' && state !== 'pending') {
      touched.push({x: parseFloat(el.style.left), y: parseFloat(el.style.top)});
    }
  });
  const stage = mapStage();
  if (!touched.length) return mapFit();
  const pad = 140;
  const x0 = Math.min(...touched.map(n => n.x)) - pad;
  const y0 = Math.min(...touched.map(n => n.y)) - pad;
  const x1 = Math.max(...touched.map(n => n.x)) + 178 + pad;
  const y1 = Math.max(...touched.map(n => n.y)) + 52 + pad;
  const whole = Math.min(stage.width / (x1 - x0), stage.height / (y1 - y0));
  MAP_K = Math.min(1.15, Math.max(MAP_FLOOR, whole));
  // Centred on the middle of the run. When the run does not fit at this size - which is
  // the usual case - the middle is the honest place to start.
  MAP_X = stage.width / 2 - ((x0 + x1) / 2) * MAP_K;
  MAP_Y = stage.height / 2 - ((y0 + y1) / 2) * MAP_K;
  mapApply();
}

function mapFit() {
  const stage = mapStage();
  MAP_K = Math.min(stage.width / MAP_SIZE.w, stage.height / MAP_SIZE.h) * .92;
  mapGlide();
  mapApply();
}

ACTIONS.map = d => openMap(d.run);
ACTIONS.mapClose = () => closeMap();
ACTIONS.mapFit = () => mapFit();
ACTIONS.mapFocus = () => mapFocus();
ACTIONS.mapZoom = d => mapZoom(Number(d.by));
ACTIONS.mapPick = d => pickNode(d.node);
ACTIONS.mapStep = d => mapStep(Number(d.by));
ACTIONS.mapCopy = () => {
  const link = location.origin + location.pathname + mapHash(MAP_RUN, MAP_PICKED);
  navigator.clipboard.writeText(link)
    .then(() => say('Link copied. It opens this run at this place.', 'good'))
    .catch(() => say(link, 'warn'));
};
/* Back to where it stopped - the reason most people open this view at all. */
ACTIONS.mapStop = () => {
  const stopped = Object.keys(MAP_STATES).find(id => MAP_STATES[id] === 'failed');
  if (!stopped) return say('Nothing failed on this run.', 'warn');
  pickNode(stopped);
};
ACTIONS.mapFilter = (d, el) => {
  const showing = el.getAttribute('aria-pressed') !== 'false';
  el.setAttribute('aria-pressed', showing ? 'false' : 'true');
  $('dmap').classList.toggle('hide-' + d.state, showing);
  const off = [...document.querySelectorAll('#dmap .map-legend button[aria-pressed="false"]')]
    .map(b => b.textContent.trim());
  const note = $('dmap-hidden');
  if (note) note.textContent = off.length ? 'hiding ' + off.join(', ') : '';
  if (MAP_PICKED && $('mn-' + MAP_PICKED) && $('mn-' + MAP_PICKED).offsetParent === null) {
    pickNode(null);
  }
};

/* Every offset here is absolute pixels taken against a stage measured at the time. A
   resize - or crossing 1100px, where the side panel leaves and the stage grows by 23rem -
   makes all of them wrong, and the drawing can end up entirely off-screen. */
window.addEventListener('resize', () => {
  MAP_RECT = null;
  if (!$('dmap').classList.contains('on')) return;
  clearTimeout(MAP_RESIZE);
  MAP_RESIZE = setTimeout(() => {
    if (MAP_PICKED && $('mn-' + MAP_PICKED)) pickNode(MAP_PICKED); else mapFocus();
  }, 120);
});

(function mapFindBox() {
  const box = $('dmap-find');
  if (!box) return;
  box.addEventListener('input', mapFind);
  box.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); mapFindEnter(); }
    if (e.key === 'Escape') { e.stopPropagation(); box.value = ''; mapFind(); }
  });
})();

(function mapDrag() {
  const stage = $('dmap-stage');
  if (!stage) return;
  let from = null, origin = null, moved = false;
  stage.addEventListener('pointerdown', e => {
    // The left button only: a right-click used to start a pan and leave the stage in it
    // while the context menu was open, and a second finger overwrote the first mid-drag.
    if (e.button !== 0 || !e.isPrimary || e.target.closest('.mn')) return;
    from = {x: e.clientX - MAP_X, y: e.clientY - MAP_Y};
    origin = {x: e.clientX, y: e.clientY};
    moved = false;
    stage.classList.add('dragging');
    try { stage.setPointerCapture(e.pointerId); } catch (err) { /* nothing to capture */ }
  });
  stage.addEventListener('pointermove', e => {
    if (!from) return;
    // Measured from where the button went down, which is what a drag threshold is.
    if (Math.abs(e.clientX - origin.x) > 3 || Math.abs(e.clientY - origin.y) > 3) moved = true;
    MAP_X = e.clientX - from.x;
    MAP_Y = e.clientY - from.y;
    mapApply();
  });
  const done = () => {
    // A click on the paper rather than on a node: back to the whole run, which is what
    // "nothing in particular" means here.
    if (from && !moved && MAP_PICKED) pickNode(null);
    from = null;
    moved = false;
    stage.classList.remove('dragging');
  };
  stage.addEventListener('pointerup', done);
  stage.addEventListener('pointercancel', done);
  stage.addEventListener('wheel', e => {
    // ctrl+wheel is the browser's own zoom, and it is what a trackpad pinch arrives as.
    // Taking it away leaves a low-vision reader no way to enlarge this page.
    if (e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    // Scaled by how far the wheel actually turned: a mouse notch reports about 100 and a
    // trackpad reports single digits, so a fixed step per event makes the two unusable at
    // opposite ends - one too slow, one pinned at the limit inside a flick.
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? mapStage().height : 1;
    mapZoomTo(MAP_K * Math.exp(-e.deltaY * unit * 0.0022), {x: e.clientX, y: e.clientY});
  }, {passive: false});
})();
"""
