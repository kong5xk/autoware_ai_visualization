# Simulation fork workflow

This repository is the source of truth for the visualization packages used by
the simulation image. Do not make persistent changes only in a running
container: a replacement container will lose them and its image cannot identify
the source revision.

## Package boundaries

- Keep upstream visualization nodes and their `package.xml`/`CMakeLists.txt`
  files intact unless the node itself must change.
- Put simulator-specific vehicle data in `sim_vehicle_description`.
- Keep a vehicle mesh, its xacro/URDF, dimensions, and launch defaults in one
  commit so every revision is internally coherent.
- If a resource directory is added, add its CMake install rule in the same
  commit. Installed-space launches must not depend on source-space paths.
- Use package URIs (`package://...`) and `$(find package)` rather than absolute
  container paths.

Run the repository check before committing (and as a required job in the
fork's external CI/build pipeline):

```bash
python3 scripts/check_package_coherence.py
```

## Branch and commit sequence

Simulation work is based on the Autoware.AI `1.14.0` tag and lives on
`sim/vehicle-visualization`. Configure the remotes, fetch the immutable release
tag, and create the branch once:

```bash
git remote add origin git@github.com:<fork-owner>/autoware_ai_visualization.git
git remote add upstream https://github.com/autowarefoundation/autoware_ai_visualization.git
git fetch upstream --tags
git switch -c sim/vehicle-visualization 1.14.0
```

For each change, work on that branch, validate, commit, and push it before an
image build:

```bash
git switch sim/vehicle-visualization
python3 scripts/check_package_coherence.py
git add <coherent-set-of-files>
git diff --cached --check
git commit -m "Describe the simulation change"
git push -u origin sim/vehicle-visualization
```

Prefer reviewable commits with one concern each, for example:

1. `Fix installation of existing launch and vehicle parameters`
2. `Add simulation vehicle description package`
3. `Add package coherence checks and reproducible image build`

The branch must be pushed to the fork before an image is built. Open a pull
request from `sim/vehicle-visualization` to the fork's default branch when the
simulation configuration is stable. Preserve the branch for iterative testing;
use merge commits or squash according to the fork's review policy.

Before moving to a later upstream release, update the image base and rebase the
simulation branch onto the matching visualization tag in one reviewed change.
Do not silently combine packages from one Autoware release with another base
image.

## Build a revision-addressed image

`docker/Dockerfile` starts from the digest-pinned Autoware.AI 1.14.0 image,
clones the pushed fork, checks out the exact commit, checks package coherence,
and rebuilds the visualization packages. The wrapper refuses dirty or unpushed
revisions:

```bash
VISUALIZATION_REPOSITORY=https://github.com/<fork-owner>/autoware_ai_visualization.git \
IMAGE_NAME=ghcr.io/<fork-owner>/autoware-simulation:$(git rev-parse --short=12 HEAD) \
./docker/build-image.sh
```

For a private fork, provide build-time Git credentials using your build
infrastructure rather than embedding tokens in the repository or image. The
current Dockerfile expects a clone URL available to the builder.

After testing, publish the immutable commit tag and optionally a moving branch
tag:

```bash
docker push ghcr.io/<fork-owner>/autoware-simulation:<commit-sha>
docker tag  ghcr.io/<fork-owner>/autoware-simulation:<commit-sha> \
            ghcr.io/<fork-owner>/autoware-simulation:sim-vehicle
docker push ghcr.io/<fork-owner>/autoware-simulation:sim-vehicle
```

Deployments should pin the commit tag (or image digest), not only the moving
tag. This makes the running image traceable back to the fork commit that owns
the manifests, launch files, descriptions, and nodes.
