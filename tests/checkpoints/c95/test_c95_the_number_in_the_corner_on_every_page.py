"""Checkpoint C95 - the sheet after P170, on every page that wears it.

P170 moved the map's ordinal inside the node and gave the elevation a third layer. Both
live in shared sheets - the map's and the theme's - so the question a checkpoint asks is
whether every page that renders still gets one theme, whether the map's new rules name only
tokens the theme defines, and whether the badge geometry that was measured in isolation
still holds when the map's sheet is served inside the Activity page as the browser gets it.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from ops.console.map_view import MAP_STYLE
from tests.p170.test_the_number_in_the_corner import NODE_H, NODE_W, ROOT_PX, _badge_box, _rule
from ui.theme import CSS


def _defined_tokens() -> set[str]:
    return set(re.findall(r"--([\w-]+)\s*:", CSS))


def test_every_token_the_map_names_is_one_the_theme_defines() -> None:
    named = set(re.findall(r"var\(--([\w-]+)\)", MAP_STYLE))
    missing = named - _defined_tokens() - {"edge", "wash", "mark", "ring"}
    assert not missing, missing


def test_the_three_layer_elevation_reaches_every_served_page(tmp_path: Path) -> None:
    """The theme is one string, served into each page; a page that carried its own copy
    of the shadow would be the drift this checkpoint exists to catch."""
    from ops.console import Console
    from ops.console.app import create_app
    from ops.events import EventBus
    from ops.run_store import open_store
    from registries.contracts import ContractRegistry

    store = open_store(f"sqlite:///{(tmp_path / 'c95.db').as_posix()}")
    try:
        bus = EventBus(store, contracts=ContractRegistry.load())
        api = TestClient(create_app(Console(store, bus)))
        shadow = re.search(r"--shadow:([^;]+);", CSS).group(1)
        assert shadow.count("rgba(") == 3
        for path in ("/", "/help", "/analytics"):
            body = api.get(path).text
            assert shadow in body, path
            assert body.count("--shadow:") == 1, (path, "the token is declared once")
    finally:
        store.close()


def test_the_badge_fits_the_node_as_the_activity_page_serves_it(tmp_path: Path) -> None:
    """The map's sheet inside the page, not the Python string: the badge still lies inside
    178x52 at both ends of the fluid root, and the node still clips."""
    from ops.console import Console
    from ops.console.app import create_app
    from ops.events import EventBus
    from ops.run_store import open_store
    from registries.contracts import ContractRegistry

    store = open_store(f"sqlite:///{(tmp_path / 'c95.db').as_posix()}")
    try:
        bus = EventBus(store, contracts=ContractRegistry.load())
        page = TestClient(create_app(Console(store, bus))).get("/").text
    finally:
        store.close()
    assert "#dmap .mn .ord{" in page
    served = page[
        page.index(
            "/* ---------------------------------------------------------------- the map */"
        ) :
    ]
    served = served[: served.index("</style>")]
    near = _rule("#dmap .mn .ord", served)
    far = {**near, **_rule("#dmap.far .mn .ord", served)}
    for root in ROOT_PX:
        for rule, centred in ((near, False), (far, True)):
            left, top, right, bottom = _badge_box(rule, root, centred=centred)
            assert left >= 0 and right <= NODE_W and top >= 0 and bottom <= NODE_H, (root, rule)
    assert _rule("#dmap .mn", served)["overflow"] == "hidden"
