"""The portability claim, checked rather than asserted.

Four exit criteria, and the one thing each of them is really about: nothing in this
codebase is a fact about one machine, one vendor or one person's laptop.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import yaml

import ports
from tests.conftest import needs_a_checkout

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "HANDOFF.md"
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "compose.yaml"
DOCKERIGNORE = ROOT / ".dockerignore"
ENV_EXAMPLE = ROOT / ".env.example"

# Every package that ships. tests/ is not one, and neither is the virtualenv.
SHIPPED = tuple(
    sorted(
        p.name
        for p in ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file() and p.name not in {"tests"}
    )
)

# A managed-service primitive is a thing that only exists inside one vendor's platform.
# Depending on one is how "any host" quietly becomes "that host". The SDKs are listed by
# import name; the runtime shapes by the symbol that only appears when you are inside one.
MANAGED_SERVICE_IMPORTS = (
    "boto3", "botocore", "aiobotocore",
    "azure.functions", "azure.servicebus", "azure.cosmos", "azure.storage",
    "google.cloud", "google.appengine", "firebase_admin",
    "sagemaker", "vertexai", "databricks",
)
MANAGED_SERVICE_SYMBOLS = (
    "lambda_handler",
    "AWS_LAMBDA_FUNCTION_NAME",
    "AWS_EXECUTION_ENV",
    "FUNCTIONS_WORKER_RUNTIME",
    "WEBSITE_INSTANCE_ID",
    "K_SERVICE",
    "GAE_APPLICATION",
    "DYNAMO",
    "CosmosClient",
    "ServiceBusClient",
)

ENV_PATTERN = re.compile(
    r'"(AA_[A-Z0-9_]+|ANTHROPIC_API_KEY|SHAREFILE_[A-Z_]+|BOX_[A-Z_]+)"'
)


def shipped_files() -> list[Path]:
    found: list[Path] = []
    for package in SHIPPED:
        found.extend(sorted((ROOT / package).rglob("*.py")))
    return [p for p in found if "__pycache__" not in p.parts]


# ============================================================ no managed service


def test_no_managed_service_primitive_is_depended_on_anywhere() -> None:
    """The exit criterion, and the deployment argument in one test.

    One `import boto3` and the deployment target stops being an environment and becomes
    an architecture. Checked over imports rather than over prose, because the failure is
    invisible: the code works perfectly until the day it has to move.
    """
    offenders: list[str] = []
    for path in shipped_files():
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == m or name.startswith(m + ".") for m in MANAGED_SERVICE_IMPORTS):
                    offenders.append(f"{path.relative_to(ROOT)}: imports {name}")
        for symbol in MANAGED_SERVICE_SYMBOLS:
            if symbol in source:
                offenders.append(f"{path.relative_to(ROOT)}: names {symbol}")
    assert offenders == [], offenders


def test_the_dependency_list_names_no_vendor_sdk() -> None:
    """The other half: nothing arrives as a dependency either."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for vendor in ("boto3", "azure-", "google-cloud", "firebase", "databricks", "sagemaker"):
        assert vendor not in pyproject, vendor


def test_every_deployment_choice_is_a_port() -> None:
    """Six ports, and the two that are contracts for the firm's connectors are declared
    rather than absent - so choosing one is a refusal somebody can read."""
    assert set(ports.PORTS) == {"storage", "delivery", "secrets", "queue", "llm", "compute"}
    assert ports.contracts("storage") == ("sharefile",)
    assert ports.contracts("delivery") == ("box",)
    assert "local_folder" in ports.ready("storage") and "local_folder" in ports.ready("delivery")
    for port in ports.PORTS:
        assert ports.ready(port), f"{port} has no adapter that can be built"


# ============================================================ nothing undocumented


def test_every_environment_variable_the_code_reads_is_in_the_env_example() -> None:
    """"A clean clone plus .env with no undocumented step" is only true if the example
    file names every variable. Derived from the source, so a variable added without being
    documented fails here rather than on somebody's first evening with the repo."""
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    read: dict[str, str] = {}
    for path in shipped_files():
        for name in ENV_PATTERN.findall(path.read_text(encoding="utf-8")):
            read.setdefault(name, str(path.relative_to(ROOT)))
    assert len(read) >= 20, "the scan found suspiciously few variables"
    missing = {name: where for name, where in read.items() if name not in example}
    assert missing == {}, missing


def test_the_env_example_carries_no_credential() -> None:
    """It is committed. A real key in it is a key in the git history forever."""
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "sk-ant-..." in example, "the placeholder is a placeholder"
    assert not re.search(r"sk-ant-[A-Za-z0-9_-]{20,}", example)
    assert re.search(r"^AA_VAULT_KEY=\s*$", example, re.MULTILINE), "the vault key is blank"
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_the_handoff_names_every_environment_difference() -> None:
    """The exit criterion. Each row of the difference table is a variable or an adapter
    that actually exists, so the document cannot drift from the code silently."""
    handoff = HANDOFF.read_text(encoding="utf-8")
    for named in (
        "ANTHROPIC_API_KEY", "AA_VAULT_KEY", "AA_STORAGE_ADAPTER", "AA_DELIVERY_ADAPTER",
        "AA_DB_URL", "AA_MAX_PARALLELISM", "sharefile", "box", "redis_rq", "local_folder",
    ):
        assert named in handoff, named
    for section in ("Get it running", "In a container", "the work machine",
                    "three work repos", "still owed"):
        assert section in handoff, section
    assert "Docker Desktop is\nnot licensed here" in handoff or "not licensed" in handoff
    assert "Client data never enters the repo" in handoff


def test_the_handoff_says_which_runtime_was_actually_used() -> None:
    """The exit criterion asks which runtime the proof was actually run on.

    That is a fact about history, not about whatever machine happens to be reading the
    packet - so it is not conditioned on what is installed here. Either the packet names
    a runtime, a version and a date, or it says plainly that the image has never been
    built. A version and a date, because "we used podman" is not something a colleague
    can reproduce or date.
    """
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "Which runtime was actually used" in handoff
    block = handoff[handoff.index("Which runtime was actually used") :][:2000]

    if "has never been built" in block:
        return  # the honest unproven form, until somebody runs it

    named = [r for r in ("docker", "podman", "nerdctl", "finch") if r in block.lower()]
    assert named, "the packet claims a run but names no runtime"
    assert re.search(r"\d+\.\d+\.\d+", block), "a runtime without a version"
    assert re.search(r"20\d\d-\d\d-\d\d", block), "a run without a date"
    assert "Docker Desktop" in block, "say what it was not, since that is the constraint"


def owed_on_the_work_machine() -> tuple[list[str], list[str]]:
    """The plan's work-machine tasks, and the register's rows for them.

    Two records of the same thing, kept apart on purpose: the plan is what the gate
    reads, the register is what a person reads. Returning both lets a test assert they
    agree rather than assert a number, which is what actually matters - a literal count
    goes stale the moment somebody defers a fifth thing, and then three tests fail for a
    reason that has nothing to do with what they guard.
    """
    import json

    plan = json.loads((ROOT / "BUILD" / "plan.json").read_text(encoding="utf-8"))
    p28 = next(p for p in plan["phases"] if p["id"] == "P28")
    tasks = [t for t in p28["tasks"] if t.startswith("On the work machine")]

    register = (ROOT / "BUILD" / "OPEN.md").read_text(encoding="utf-8")
    section = register[register.index("## 3. Evidence only the work machine") :]
    section = section[: section.index("\n\nTwo more")]
    rows = [
        line for line in section.splitlines()
        if line.startswith("| **") and "What is owed" not in line
    ]
    return tasks, rows


def test_what_is_still_owed_is_the_phases_own_task_list() -> None:
    """The four things that need the work machine are in the plan and in the packet, so
    neither can quietly lose one."""
    owed, rows = owed_on_the_work_machine()
    assert owed, "nothing is owed to the work machine, which would be a first"
    assert len(owed) == len(rows), {"in the plan": owed, "in the register": rows}
    handoff = HANDOFF.read_text(encoding="utf-8")
    for fragment in ("taxonomy", "add-backs", "model builder", "timing normalization"):
        assert fragment.lower() in handoff.lower(), fragment


# ============================================================ the image


def test_the_dockerfile_builds_from_the_lock_and_bakes_in_no_secret() -> None:
    """What is in a layer is in every copy of that image, forever."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "uv.lock" in text and "--frozen" in text, "built from the lock, not from a resolve"
    assert "python:3.12-slim" in text
    assert "USER analyst" in text and "useradd" in text, "not root"
    assert "VOLUME" in text, "client data lives on a volume, never in a layer"
    for forbidden in ("ANTHROPIC_API_KEY", "AA_VAULT_KEY", "SHAREFILE_", "BOX_CLIENT"):
        assert forbidden not in text, forbidden
    assert "COPY .env" not in text
    ignored = DOCKERIGNORE.read_text(encoding="utf-8")
    for path in (".env", "inbox/", "outbox/", "runs/", "vault/", "*.db"):
        assert path in ignored, path


def test_compose_brings_up_the_app_and_postgres_and_needs_no_docker_desktop() -> None:
    """Plain OCI compose: podman, nerdctl, Rancher Desktop and Docker Engine all run it."""
    spec = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert set(spec["services"]) == {"app", "db"}
    app, db = spec["services"]["app"], spec["services"]["db"]
    assert app["depends_on"]["db"]["condition"] == "service_healthy"
    assert "postgresql+psycopg://" in app["environment"]["AA_DB_URL"]
    assert app["command"][-1] == "--postgres", "the suite runs against Postgres in compose"
    assert db["image"].startswith("postgres:")
    assert "healthcheck" in db

    # The configuration, not the comment that explains the rule.
    configuration = "\n".join(
        line for line in COMPOSE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    for desktop_only in (
        "desktop.", "npipe://", "host.docker.internal", "/var/run/docker.sock", "credsStore",
    ):
        assert desktop_only not in configuration, desktop_only
    assert app["env_file"] == [".env"], "credentials come from .env at run time"


def test_the_image_is_built_and_the_suite_runs_inside_it(container_runtime: str) -> None:
    """The exit criterion that needs a machine with a runtime on it.

    Opt in with `pytest --container`. Without it the session summary says, in words, that
    the image was never built - the same honesty the Postgres and Redis runs get, and for
    the same reason: a claim nobody has executed is not evidence.
    """
    build = subprocess.run(  # noqa: S603 - the runtime name comes from a closed set
        [container_runtime, "build", "-t", "automated-analyst:test", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]

    # The image's own command, not one of ours - what a colleague gets when they run it
    # with no arguments is the thing being proved.
    run = subprocess.run(  # noqa: S603
        [container_runtime, "run", "--rm", "automated-analyst:test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-8000:] + run.stderr[-4000:]
    assert "passed" in run.stdout + run.stderr, "the suite ran on the image's interpreter"


def test_a_clean_clone_reaches_a_passing_suite_with_no_undocumented_step() -> None:
    """What a colleague actually gets, asked of git rather than of the working tree.

    Everything the packet tells a newcomer to run has to be tracked - the lock, the env
    example, the container files, the gate - and nothing that holds a credential or a
    client file may be. Not the whole suite: that is what the run they are told to do
    proves, and running it twice inside itself would double the slowest thing in the build.
    """
    needs_a_checkout("what a colleague gets")
    tracked = set(
        subprocess.run(  # noqa: S603
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    assert len(tracked) > 200, "the index looks empty"

    for needed in (
        "pyproject.toml", "uv.lock", ".env.example", "HANDOFF.md", "Dockerfile",
        "compose.yaml", ".dockerignore", "README.md", "CLAUDE.md",
        "tools/gate.py", "tools/postgres.py", "tools/postgres-init.sh",
        "tests/conftest.py", "BUILD/plan.json",
    ):
        assert needed in tracked, needed
    for package in SHIPPED:
        assert f"{package}/__init__.py" in tracked, package

    # And nothing that must never be committed is.
    assert ".env" not in tracked, "a secret is in the history"
    for path_ in sorted(tracked):
        assert not path_.startswith(("runs/", "vault/", "inbox/", "outbox/", "artifacts/")), path_
        assert not path_.endswith((".db", ".sqlite3")), path_

    # The steps the packet names resolve to things that exist.
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "uv sync --all-groups" in handoff
    assert "cp .env.example .env" in handoff


def test_the_import_boundary_covers_every_package_that_ships() -> None:
    """The boundary test is the portability guarantee, and it is only worth what it
    scans. Packages added after P03 were not on its list."""
    from tests.p03.test_boundary import SCANNED

    uncovered = sorted(set(SHIPPED) - set(SCANNED) - {"ports"})
    assert uncovered == [], uncovered
