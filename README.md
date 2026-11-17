# GTE Engine Lab

[Open the interactive 3D engine lab](https://gideonamani.github.io/GTEWebMockups-Viewer/)

Explore gas turbine engine teaching models in your browser. Rotate and section the
assemblies, identify their components, follow illustrative rotation and airflow,
and practise with touch activities. The viewer works on desktop and phones.

Dimensions and motion described as illustrative are teaching reconstructions;
source references and scope are available inside each engine's learning panels.

This public repository holds deployment code and validation records. The approved
website ZIP is a release asset and is deployed as a GitHub Pages artifact. Native
CAD, Blender and STEP archives, engineering source code, manuals and source media
are kept in the private engineering project. Model binaries are never committed
to this repository's Git history.

Every release is pinned in `docs/github-pages-release.json`. Its archive contains
a complete file inventory and passing release checks. The deployment workflow
verifies the archive before publication. The repository's `PAGES_ENABLED` Actions
variable enables automatic deployment when the release descriptor changes.
