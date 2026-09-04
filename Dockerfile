# One image, any host. No managed-service primitive, no Docker Desktop, no host Python.
#
# Two stages so the thing that ships holds no build tooling. The dependency layer is
# installed from uv.lock alone, before the source is copied, so editing a module does not
# reinstall pandas - and, more importantly, so the image is built from the same pinned
# versions the suite passed against rather than from whatever resolved that morning.
#
# The image contains no credential and no client data. Both arrive at runtime: secrets
# through the environment (the Secrets Port reads them; feature code never does), and
# files through mounted volumes. See HANDOFF.md.

FROM python:3.12-slim-bookworm AS deps

# uv is pinned by digest-bearing tag rather than installed with a script that fetches
# "latest": a build that resolves a different toolchain each time is not reproducible,
# which is the whole claim this image is here to make.
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies only. --frozen refuses to update the lock: if pyproject.toml and uv.lock
# disagree, the build fails rather than quietly resolving something nobody tested.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --all-groups


FROM python:3.12-slim-bookworm AS runtime

# libgomp1 is pandas' one non-Python runtime dependency on slim. Nothing else is added:
# every other thing this system needs is Python, which is the point of the stack choice.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# A non-root user, and the run artifacts owned by it. A container that writes as root
# leaves files on a mounted volume that the person on the host cannot delete.
RUN useradd --create-home --uid 1000 analyst
WORKDIR /app

COPY --from=deps --chown=analyst:analyst /app/.venv /app/.venv
COPY --chown=analyst:analyst . /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AA_INBOX_ROOT=/data/inbox \
    AA_OUTBOX_ROOT=/data/outbox \
    AA_DB_URL=sqlite:////data/runs/run_store.db \
    AA_WORKDIR=/tmp/aa \
    AA_SKILLS_INTAKE_ROOT=/data/skills-intake \
    AA_IMAGE=automated-analyst:0.1.0

# Everything that holds client data is a volume, so nothing of a client's survives in a
# layer. The image is publishable; the volumes are not.
VOLUME ["/data"]

USER analyst

# The default is the suite, because the first thing anybody does with this image on a new
# machine is ask whether it works here.
CMD ["python", "-m", "pytest", "-q"]
