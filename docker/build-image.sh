#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git -C "$(dirname "${BASH_SOURCE[0]}")/.." rev-parse --show-toplevel)"
repository="${VISUALIZATION_REPOSITORY:-$(git -C "${repo_root}" config --get remote.origin.url 2>/dev/null || true)}"
ref="${VISUALIZATION_REF:-$(git -C "${repo_root}" branch --show-current)}"
sha="${VISUALIZATION_SHA:-$(git -C "${repo_root}" rev-parse HEAD)}"
image="${IMAGE_NAME:-autoware-simulation:${sha:0:12}}"
base_image="${AUTOWARE_BASE_IMAGE:-autoware/autoware:1.14.0-melodic@sha256:883aa8df23a0dd2fe6914ad159ce9c25d76a2b7a63e5eb90dba5dc33f29ecae4}"

if [[ -z "${repository}" ]]; then
  echo "Set VISUALIZATION_REPOSITORY to the URL of the pushed fork." >&2
  exit 2
fi
if [[ "${repository}" =~ ^https?://[^/]*@ ]]; then
  echo "Refusing a repository URL with embedded credentials; use a public URL or build secrets." >&2
  exit 2
fi
if [[ -z "${ref}" ]]; then
  echo "A branch name is required; detached HEAD builds must set VISUALIZATION_REF." >&2
  exit 2
fi
if [[ -n "$(git -C "${repo_root}" status --porcelain)" ]]; then
  echo "Refusing to build from an uncommitted tree; commit and push the changes first." >&2
  exit 2
fi
if ! git -C "${repo_root}" branch --remotes --contains "${sha}" | grep -q .; then
  echo "Refusing to build: ${sha} is not present on a known remote branch. Push it first." >&2
  exit 2
fi
if [[ "${ALLOW_ANY_BRANCH:-0}" != "1" ]] \
   && ! git -C "${repo_root}" merge-base --is-ancestor "${sha}" "origin/${ref}" 2>/dev/null; then
  echo "Refusing to build: ${sha} is not on origin/${ref}. Push this branch or set ALLOW_ANY_BRANCH=1." >&2
  exit 2
fi

python3 "${repo_root}/scripts/check_package_coherence.py"

docker build \
  --file "${repo_root}/docker/Dockerfile" \
  --build-arg "AUTOWARE_BASE_IMAGE=${base_image}" \
  --build-arg "VISUALIZATION_REPOSITORY=${repository}" \
  --build-arg "VISUALIZATION_REF=${ref}" \
  --build-arg "VISUALIZATION_SHA=${sha}" \
  --tag "${image}" \
  "${repo_root}"

printf 'Built %s from %s at %s\n' "${image}" "${repository}" "${sha}"
