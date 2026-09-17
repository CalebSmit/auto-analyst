"""P43: an engagement's files from the Setup page - where they go, what is there, and adding one.

A person with a client's statements should not have to work out a folder path. What is tested
is that the page can only ever do what dropping a file in the folder would: one file, by name,
inside the engagement's own folder, recorded against the person - and nothing on a machine
whose storage is not a local folder, or for an engagement that is archived.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin import AdminConsole
from admin import console as admin_console
from admin.app import create_admin_app
from tests.p24.conftest import HEND, WHO

FOLDER = Path("Clients") / "Henderson Manufacturing" / "2026 ESOP"


def test_the_files_panel_says_where_they_go_and_what_is_there(
    console: AdminConsole, henderson: Any, environment: dict[str, Path]
) -> None:
    (environment["inbox"] / FOLDER / "TB_2025.xlsx").write_bytes(b"workbook")
    shown = console.engagement_files(HEND)
    assert shown["relative"] == FOLDER.as_posix()
    assert Path(shown["absolute"]) == environment["inbox"] / FOLDER
    assert shown["can_add"] is True
    assert [f["path"] for f in shown["files"]] == ["TB_2025.xlsx"]
    assert shown["files"][0]["bytes"] == len(b"workbook")


def test_a_file_lands_in_the_folder_and_the_change_is_recorded(
    console: AdminConsole, henderson: Any, environment: dict[str, Path]
) -> None:
    data = b"income statement bytes"
    placed = console.add_file(
        HEND, "FY2025 Income Statement.xlsx", data, who=WHO, reason="from client"
    )
    target = environment["inbox"] / FOLDER / "FY2025 Income Statement.xlsx"
    assert target.read_bytes() == data
    assert placed["digest"] == "sha256:" + hashlib.sha256(data).hexdigest()
    assert placed["replaced"] is False

    (logged,) = [c for c in console.config.changes() if c.field == f"files/{HEND}"]
    assert logged.who == WHO and logged.new["digest"] == placed["digest"]

    again = console.add_file(
        HEND, "FY2025 Income Statement.xlsx", b"v2", who=WHO, reason="restated"
    )
    assert again["replaced"] is True, "a replaced file says so on the record"


@pytest.mark.parametrize(
    "name",
    ["..", "a/..", ".hidden", "", "bad:name.xlsx", "tab\tname.xlsx"],
)
def test_only_a_plain_file_name_is_accepted(
    console: AdminConsole, henderson: Any, name: str
) -> None:
    with pytest.raises(ValueError):
        console.add_file(HEND, name, b"x", who=WHO, reason="r")


def test_a_path_in_the_name_is_reduced_to_the_name(
    console: AdminConsole, henderson: Any, environment: dict[str, Path]
) -> None:
    """A browser can send a path; only its last part is ever used, so the file stays in the
    engagement's own folder."""
    console.add_file(HEND, "..\\..\\other client\\TB.xlsx", b"x", who=WHO, reason="r")
    assert (environment["inbox"] / FOLDER / "TB.xlsx").is_file()
    assert not (environment["inbox"] / "other client").exists()


def test_empty_oversized_and_unexplained_files_are_refused(
    console: AdminConsole, henderson: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="empty"):
        console.add_file(HEND, "a.xlsx", b"", who=WHO, reason="r")
    with pytest.raises(ValueError, match="reason"):
        console.add_file(HEND, "a.xlsx", b"x", who=WHO, reason=" ")
    monkeypatch.setattr(admin_console, "MAX_UPLOAD_BYTES", 4)
    with pytest.raises(ValueError, match="larger"):
        console.add_file(HEND, "a.xlsx", b"12345", who=WHO, reason="r")


def test_an_archived_engagement_takes_no_more_files(console: AdminConsole, henderson: Any) -> None:
    console.archive(HEND, who=WHO, reason="engagement closed")
    assert console.engagement_files(HEND)["can_add"] is False
    with pytest.raises(ValueError, match="archived"):
        console.add_file(HEND, "late.xlsx", b"x", who=WHO, reason="r")


def test_storage_that_is_not_a_local_folder_is_not_written_from_the_page(
    console: AdminConsole, henderson: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console.preflight.storage, "name", "box", raising=False)
    assert console.engagement_files(HEND)["can_add"] is False
    with pytest.raises(ValueError, match="local folder"):
        console.add_file(HEND, "a.xlsx", b"x", who=WHO, reason="r")


def test_an_unknown_engagement_is_named(console: AdminConsole) -> None:
    with pytest.raises(KeyError, match="not on the roster"):
        console.engagement_files("NOPE-2026-01")


def test_over_http_a_file_is_uploaded_and_bad_content_is_refused(
    console: AdminConsole, henderson: Any, environment: dict[str, Path]
) -> None:
    client = TestClient(create_admin_app(console))
    body = {"who": WHO, "reason": "over http", "name": "BS.xlsx"}
    sent = client.post(
        f"/api/admin/engagements/{HEND}/files",
        json={**body, "content_base64": base64.b64encode(b"balance sheet").decode()},
    )
    assert sent.status_code == 200, sent.text
    assert (environment["inbox"] / FOLDER / "BS.xlsx").read_bytes() == b"balance sheet"
    listed = client.get(f"/api/admin/engagements/{HEND}/files").json()
    assert [f["path"] for f in listed["files"]] == ["BS.xlsx"]

    garbled = client.post(
        f"/api/admin/engagements/{HEND}/files", json={**body, "content_base64": "not base64!!"}
    )
    assert garbled.status_code == 400
    escaping = client.post(
        f"/api/admin/engagements/{HEND}/files",
        json={**body, "name": "..", "content_base64": base64.b64encode(b"x").decode()},
    )
    assert escaping.status_code == 400


def test_a_methodology_file_can_be_read_where_it_is_cleared(console: AdminConsole) -> None:
    register = console.preflight.methodology
    name = register.name_of(register.files()[0])
    shown = console.methodology_text(name)
    assert shown["name"] == name and shown["text"].strip()
    client = TestClient(create_admin_app(console))
    assert client.get(f"/api/admin/methodology/{name}/text").json()["text"] == shown["text"]
    assert client.get("/api/admin/methodology/no/such.md/text").status_code == 400
