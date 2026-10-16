#!/usr/bin/env bash
# Build the delivery image, run its self-test, and report the identifiers the
# manifest needs. Run from the repository root.
#
#   scripts/build_image.sh [tag]        # default tag: norma-qaoa:0.1.0
#
# The image digest is not known until the image exists, and a process cannot read
# its own digest, so the run command below passes it in as an environment variable.
# That is what lands in the manifest under `container.image_digest` (spec p.19).
set -euo pipefail

TAG="${1:-norma-qaoa:0.1.0}"
BUILT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

command -v docker >/dev/null 2>&1 || {
  echo "docker not found on PATH. This script needs a working docker CLI." >&2
  exit 127
}

echo "==> building ${TAG}"
docker build --tag "${TAG}" --label "org.opencontainers.image.created=${BUILT_UTC}" .

echo
echo "==> self-test inside the image"
docker run --rm "${TAG}" --selftest

# Image ID is always available locally. RepoDigests exist only once the image has been
# pushed to (or pulled from) a registry, so it is empty on a freshly built local image.
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${TAG}")"
REPO_DIGEST="$(docker image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' "${TAG}")"
BASE_DIGEST="$(docker image inspect --format '{{index .RepoDigests 0}}' python:3.12-slim-bookworm 2>/dev/null || echo 'unresolved (base image not pulled by digest)')"

echo
echo "==> identifiers"
echo "  tag          : ${TAG}"
echo "  image id     : ${IMAGE_ID}"
echo "  repo digest  : ${REPO_DIGEST:-<none; push to a registry to obtain one>}"
echo "  base image   : ${BASE_DIGEST}"
echo "  built (UTC)  : ${BUILT_UTC}"

DIGEST="${REPO_DIGEST:-${IMAGE_ID}}"

cat <<EOF

==> run one job

  mkdir -p job out && cp fixtures/synthetic_12_6.json job/request.json
  docker run --rm \\
    -v "\$PWD/job:/in:ro" -v "\$PWD/out:/out" \\
    -e NORMA_IMAGE_REF="${TAG}" \\
    -e NORMA_IMAGE_DIGEST="${DIGEST}" \\
    -e NORMA_IMAGE_BUILT_UTC="${BUILT_UTC}" \\
    --user "\$(id -u):\$(id -g)" \\
    ${TAG}

  Artifacts land in ./out as result.json and manifest.json. Exit codes are documented
  in docs/container-operations.md; 0 and 1 mean a result was written.
EOF
