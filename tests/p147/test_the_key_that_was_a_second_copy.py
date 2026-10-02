"""P147: a key that said things the drawing it belongs to does not.

The Run trace draws 118 nodes and colours the ones this run touched. Above them sits a key
of five swatches, written by hand as five inline styles. Measured in the browser against the
nodes they stand for, **all five disagreed**:

| the key said | the node is | |
|---|---|---|
| passed, a mint box with a solid green ring | a mint box with a *pale* green ring | the ring |
| failed, a solid plum block `#512a44` | a pale pink box `#f7eff4` | nothing alike |
| running, a solid blue block `#4f758b` | a pale blue box `#eef3f6` | nothing alike |
| touched, a solid grey block `#696f71` | a near-white box `#f7f6f1` | nothing alike |
| never reached, a bordered square | **no box at all** | the one that matters |

The last line is the one with consequence, and the panel's own sentence says why: *"never
ran and passed are the two answers it matters most not to confuse."* The key drew both of
them as a pale bordered square.

**This exact defect was found and fixed once already, in the other key.** `map_view.py` says
so in words: *"its swatches are the node's own rules rather than a second copy of them,
which had already drifted: the node is dashed and the swatch was solid, on the one
distinction this view is about."* The map's key uses `<i class="mn passed">` - the node's own
class. This one used `<i style="background:var(--bad)">`.

So the key is the nodes now. Each entry is a real `.node` of its state carrying its own
name, which makes it self-demonstrating: a reader sees the same chip in the key and in the
drawing because it *is* the same chip. And the fifth state is said rather than drawn, because
drawing a box for the state whose whole appearance is *not having a box* is how the two
answers came to look alike.
"""

from __future__ import annotations

import re

from ops.console.app import PAGE as ACTIVITY
from ui.theme import CSS


def legend_markup() -> str:
    """The key, as it is written in the page."""
    block = re.search(r'<div class="legend">(.*?)</div>', ACTIVITY, re.S)
    assert block, "the trace has no key"
    return block.group(1)


def node_states() -> set[str]:
    """Every state the stylesheet gives a `.node` an appearance for."""
    return set(re.findall(r"^\.node\.(\w+)\{", CSS, re.M))


def shown_states() -> set[str]:
    """Every state the key draws, read off its markup."""
    return set(re.findall(r'class="node (\w+)"', legend_markup()))


# ------------------------------------------------- the key is drawn by the drawing's rules


def test_the_key_carries_no_colour_of_its_own() -> None:
    """Five inline styles were five places a state's appearance was decided. There is one
    now, and it is the rule the drawing uses."""
    for swatch in re.findall(r"<(?:span|i)[^>]*>", legend_markup()):
        if "class=\"node" not in swatch and "ring" not in swatch and "id" not in swatch:
            continue
        assert "style=" not in swatch, f"the key paints a swatch itself: {swatch[:70]}"
    assert "background:var(" not in legend_markup(), "the key still sets a background"
    assert "box-shadow:" not in legend_markup(), "the key still sets a ring"


def test_every_state_the_key_draws_is_drawn_by_the_nodes_own_rule() -> None:
    """The property the browser confirmed: fill, ring, colour, weight, radius and padding
    identical, because there is one rule and both of them use it."""
    for state in shown_states():
        assert f".node.{state}{{" in CSS, f"the key draws {state!r} and no node rule defines it"


def test_the_key_and_the_drawing_show_the_same_set_of_states() -> None:
    """Both directions. A sixth state added to the stylesheet with no entry in the key is a
    colour on the screen that nothing explains; an entry with no rule is a swatch that
    renders as nothing."""
    assert shown_states() == node_states(), (
        f"the key draws {sorted(shown_states())} and the nodes have {sorted(node_states())}"
    )


def test_a_swatch_is_a_real_node_rather_than_a_square_beside_a_word() -> None:
    """What makes it self-demonstrating: the same markup the trace builds for a node, so a
    reader meets the same chip twice rather than a sample of one."""
    built = re.search(r'<span class="node \$\{esc\(state\)\}"[^>]*>\s*'
                      r"\$\{running \? '<i class=\"ring\"></i>' : ''\}"
                      r'<span class="id">', ACTIVITY)
    assert built, "the trace no longer builds a node the way this test assumes"
    for state in shown_states():
        entry = re.search(rf'<span class="node {state}">(.*?)</span></span>', legend_markup())
        assert entry, f"{state} is not written as a node"
        assert '<span class="id">' in entry.group(1), f"{state} carries no name of its own"
    running = re.search(r'<span class="node active">(.*?)</span></span>', legend_markup())
    assert running and '<i class="ring"></i>' in running.group(1), (
        "the running entry has lost the spinner the drawing gives it"
    )


# ------------------------------- and the state whose appearance is having none is not drawn


def test_the_state_with_no_box_is_said_and_not_drawn() -> None:
    """The defect with consequence. A node this run never reached has no fill, no ring and
    no border - that is the whole of what it looks like - and the key drew a bordered square
    for it, beside the pale square it drew for passed.
    """
    markup = legend_markup()
    assert not re.search(r'class="node"\s*>', markup), (
        "the key draws a box for the state that has none"
    )
    assert "never reached" in markup, "the key no longer mentions the state at all"
    note = re.search(r'<span class="legend-note">([^<]*)</span>', markup)
    assert note, "it is neither drawn nor said"
    assert "no box" in note.group(1), (
        f"it is said without saying what to look for: {note.group(1)!r}"
    )


def test_the_base_node_really_has_nothing_to_draw() -> None:
    """The fact the entry above rests on. If a plain node ever gains a border, the key
    should go back to drawing one - and this fails first and says so."""
    base = re.search(r"\n\.node\{([^}]*)\}", CSS)
    assert base, "the node has no base rule"
    assert "background:transparent" in base.group(1), "a plain node has a fill now"
    assert "box-shadow:none" in base.group(1), "a plain node has a ring now"


def test_the_rule_the_old_swatches_used_is_gone() -> None:
    """`.legend i` sized and ringed the five squares. Nothing wears it now, and a rule
    nothing wears is the thing this build is most often wrong about - it would also have
    captured the running entry's spinner, which is an `<i>` inside the key."""
    assert ".legend i{" not in CSS, "the square's rule outlived the squares"
    assert ".legend .node{" in CSS, "the key's entries have no rule of their own at all"
