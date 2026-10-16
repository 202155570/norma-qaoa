# norma-qaoa — container batch delivery (integration spec D01)
#
# One job per run. Mount the request in, mount a directory out:
#
#   docker build -t norma-qaoa:0.1.0 .
#   docker run --rm -v "$PWD/job:/in:ro" -v "$PWD/out:/out" norma-qaoa:0.1.0
#
# The image carries its own acceptance check:
#
#   docker run --rm norma-qaoa:0.1.0 --selftest
#
# Base image: pinned to an exact tag, not a digest. The digest of this tag cannot be
# resolved without a registry, so writing one here would be a guess. scripts/build_image.sh
# resolves the digest after the build and prints it; pass it back in at run time as
# NORMA_IMAGE_DIGEST so it lands in the manifest (spec p.19, "SDK·컨테이너 digest").
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="norma-qaoa" \
      org.opencontainers.image.description="QAOA asset-selection engine, simulator only" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="NORMA" \
      org.opencontainers.image.licenses="NONE"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NORMA_IN_DIR=/in \
    NORMA_OUT_DIR=/out

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY fixtures ./fixtures
COPY docker/entrypoint.py ./docker/entrypoint.py

# The rustworkx ceiling in pyproject.toml exists because rustworkx 0.18.1's DLL is
# blocked by Windows Smart App Control on the development machine. That reason does not
# exist on Linux, so the ceiling is lifted here — in this copy of the metadata only, so
# the installed distribution's metadata stays consistent with what is installed. The
# repository's pyproject.toml is not modified. The version actually installed is
# recorded in every manifest under `versions.rustworkx`.
RUN sed -i 's/"rustworkx<0\.18"/"rustworkx>=0.18"/' pyproject.toml \
 && pip install --no-cache-dir . \
 && python -c "import rustworkx, qiskit, qiskit_aer; \
print('rustworkx', rustworkx.__version__, '| qiskit', qiskit.__version__)"

# Non-root. /out must be writable by this user; the host directory's ownership decides
# that, so the run command may need --user "$(id -u):$(id -g)".
RUN useradd --create-home --uid 10001 norma \
 && mkdir -p /in /out \
 && chown norma:norma /in /out
USER norma

VOLUME ["/in", "/out"]

# A self-test costs one simulator run and proves the mount contract and the schema.
HEALTHCHECK NONE

ENTRYPOINT ["python", "/app/docker/entrypoint.py"]
CMD []
