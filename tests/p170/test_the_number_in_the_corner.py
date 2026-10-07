"""P170 - the number in the corner.

The order a run touched a node in is the one thing the whole-design view can say that the
trace panel cannot, and every one of those numbers was a quarter-circle: the badge hung
outside a box that clips its own overflow. These tests measure the stylesheet's own numbers
rather than trusting a sentence about them - the badge's extent at both zooms, from the
root sizes the sheet declares - and were each proved by putting the badge back outside.
"""

from __future__ import annotations

import re

from ops.console.map_view import MAP_STYLE
from ui.theme import CSS

NODE_W, NODE_H = 178, 52
ROOT_PX = (12.0, 14.5)
"""The fluid root's floor and ceiling: `clamp(12px,.55vw + 5.5px,14.5px)`."""


def _rule(selector: str, sheet: str = MAP_STYLE) -> dict[str, str]:
    """The effective declarations for exactly this selector: every rule whose selector list
    names it, merged in sheet order the way the cascade would for equal specificity."""
    bare = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    merged: dict[str, str] = {}
    found = False
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", bare):
        selectors = [s.strip() for s in match.group(1).split(",")]
        if selector in selectors:
            found = True
            for d in (x.strip() for x in match.group(2).split(";")):
                if ":" in d:
                    key, value = d.split(":", 1)
                    merged[key.strip()] = value.strip()
    if not found:
        raise AssertionError(f"no rule for {selector!r}")
    return merged


def _tokens() -> dict[str, str]:
    return dict(re.findall(r"--(t-[\w-]+):\s*([\d.]+rem)", CSS))


def _px(value: str, root: float) -> float:
    """A length in px at a given root. Only rem and px occur here; anything else fails."""
    value = value.strip()
    if value.startswith("var(--"):
        value = _tokens()[value[6:-1]]
    if value.endswith("rem"):
        return float(value[:-3]) * root
    if value.endswith("px"):
        return float(value[:-2])
    if value == "0":
        return 0.0
    raise AssertionError(f"not a length this test can measure: {value!r}")


def _badge_box(
    rule: dict[str, str], root: float, *, centred: bool
) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the badge inside a node at this root, for a two-digit
    number - the widest a run of the blueprint's size writes."""
    h = _px(rule["height"], root)
    digits = 2 * _px(rule["font-size"], root) * 0.62
    pad = 2 * _px(rule.get("padding", "0 0").split()[-1], root)
    w = max(_px(rule["min-width"], root), digits + pad)
    right = NODE_W - _px(rule["right"], root)
    if centred:
        top = NODE_H / 2 - h / 2
    else:
        top = _px(rule["top"], root)
    return right - w, top, right, top + h


def test_the_badge_lies_inside_the_node_at_the_near_zoom() -> None:
    """Both offsets non-negative, and the whole badge inside 178x52 at the root's floor and
    ceiling. The old values were -.6rem and -.5rem."""
    rule = _rule("#dmap .mn .ord")
    assert not rule["top"].startswith("-") and not rule["right"].startswith("-"), rule
    for root in ROOT_PX:
        left, top, right, bottom = _badge_box(rule, root, centred=False)
        assert left >= 0 and right <= NODE_W, (root, left, right)
        assert top >= 0 and bottom <= NODE_H, (root, top, bottom)


def test_the_badge_lies_inside_the_node_at_the_far_zoom() -> None:
    """Far out the badge is bigger and the box is a solid fill; it sits at the right edge,
    vertically centred, and every state's badge is on paper - because the near rules paint
    the `active` and `failed` badges in the fill's own colour."""
    far = _rule("#dmap.far .mn .ord")
    near = _rule("#dmap .mn .ord")
    merged = {**near, **far}
    assert far["top"] == "50%" and "translateY(-50%)" in far["transform"]
    for root in ROOT_PX:
        left, top, right, bottom = _badge_box(merged, root, centred=True)
        assert left >= 0 and right <= NODE_W, (root, left, right)
        assert top >= 0 and bottom <= NODE_H, (root, top, bottom)
    assert far["background"] == "var(--surface)" and far["color"] == "var(--navy)"
    head = MAP_STYLE[: MAP_STYLE.index("#dmap.far .mn .ord")]
    selectors = re.findall(r"\n([^{}\n]*#dmap\.far \.mn \.ord[^{]*)\{", MAP_STYLE)
    assert selectors and all(
        "#dmap.far .mn.active .ord" in s and "#dmap.far .mn.failed .ord" in s for s in selectors
    ), "the far rule must outrank the state rules, or the badge vanishes into the fill"
    assert head, "sanity: the far rule is not the first thing in the sheet"


def test_the_name_and_id_give_the_badge_its_column() -> None:
    """A node with an ordinal reserves at least the badge's full extent - its width plus the
    inset - on the right of the name and the id, so a long name ends in an ellipsis before
    the number rather than under it. At both zooms."""
    near = _rule("#dmap .mn .ord")
    room = _rule("#dmap .mn[data-ord] .nm")
    assert room == _rule("#dmap .mn[data-ord] .id"), "the id gets the same room as the name"
    far = {**near, **_rule("#dmap.far .mn .ord")}
    far_room = _rule("#dmap.far .mn[data-ord] .nm")
    for root in ROOT_PX:
        left, _, _, _ = _badge_box(near, root, centred=False)
        assert _px(room["padding-right"], root) >= NODE_W - left - 0.5, root
        left, _, _, _ = _badge_box(far, root, centred=True)
        assert _px(far_room["padding-right"], root) >= NODE_W - left - 0.5, root


def test_the_sheet_still_clips_the_node_so_the_fix_is_the_badge_and_not_the_box() -> None:
    """The box keeps `overflow:hidden` and `contain`: the name's ellipsis and the leading
    mark's corners depend on them. Removing the clip would have hidden this defect while
    letting every other overflow through."""
    node = _rule("#dmap .mn")
    assert node["overflow"] == "hidden"
    assert node["contain"].startswith("layout")


def test_what_a_run_touched_has_depth_and_what_it_did_not_does_not() -> None:
    """The four states that mean something happened share the console's panel elevation and
    a top light; the dashed outline for a node never reached has neither."""
    lifted = _rule("#dmap .mn.passed")
    assert lifted["box-shadow"] == "var(--shadow)"
    assert "linear-gradient" in lifted["background-image"]
    for state in ("used", "active", "failed"):
        other = _rule(f"#dmap .mn.{state}")
        assert other["box-shadow"] == lifted["box-shadow"], state
        assert other["background-image"] == lifted["background-image"], state
    reached_not = _rule("#dmap .mn.notreached")
    assert "box-shadow" not in reached_not and "background-image" not in reached_not
    # Far out the fill is the whole statement, so the light is switched off.
    assert _rule("#dmap.far .mn")["background-image"] == "none"


def test_the_elevation_is_three_layers_in_one_token() -> None:
    """A contact shadow, a near one and a wide soft one - declared once, so every card, modal
    and map node lifts the same way. Nothing in the map writes its own shadow geometry."""
    for name in ("--shadow", "--shadow-lift"):
        value = re.search(rf"{name}:([^;]+);", CSS).group(1)
        assert value.count("rgba(") == 3, (name, value)
    for value in re.findall(r"box-shadow:([^;}]+)", MAP_STYLE):
        assert "var(--" in value or value.strip() == "none", value


def test_every_length_the_new_rules_write_is_on_the_scale() -> None:
    """rem or a token, never a pixel: the root is fluid, and a pixel would get proportionally
    smaller on a bigger monitor."""
    for selector in (
        "#dmap .mn .ord",
        "#dmap.far .mn .ord",
        "#dmap .mn[data-ord] .nm",
        "#dmap.far .mn[data-ord] .nm",
    ):
        for key, value in _rule(selector).items():
            # A pill's 99px radius is the sheet's own convention for "round", not a length.
            if key in ("box-shadow", "transform", "background", "color", "border-radius"):
                continue
            assert "px" not in value, (selector, key, value)
