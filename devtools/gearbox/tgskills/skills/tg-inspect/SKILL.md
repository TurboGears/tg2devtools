---
name: tg-inspect
description: Use when inspecting a TurboGears project to discover routes, controllers, models, templates, or project facts. Prefer gearbox tginfo commands over guessing from files.
---

# TurboGears Project Inspection

Use `gearbox tginfo` for structured, read-only inspection instead of guessing from files. Run commands from the project root with `uv run` so the project environment is used.

`development.ini` is for local development; `test.ini` is for tests. Select the profile explicitly and do not switch profiles.

## Commands

- `uv run gearbox tginfo summary --project . --config development.ini` — package name, renderers, paths, root controller, database/auth state.
- `uv run gearbox tginfo routes --project . --config development.ini` — flat route/action rows with controller, action, params, requirements, validations, and exposures. Add `--full` for source paths, docstrings, and metadata; `--json` only when a script parses the result.
- `uv run gearbox tginfo models --project . --config development.ini` — models exported by the project model package, with ORM kind and source.
- `uv run gearbox tginfo templates --project . --config development.ini` — recognized templates and the routes that expose them.
- `uv run gearbox tginfo scaffolds --project . --config development.ini` — available scaffold templates.

RestController collection methods (`get_all`, `post`) are reported at the collection path; item methods (`get_one`, `post_delete`) at the item path. These are static dispatch descriptions; use `tgshell` for runtime request checks.

Index paths: `RootController.index` is `/`; a subcontroller index is `/subcontroller/`. Dynamic dispatch (`_lookup`, exposed `_default`) appears as synthetic rows with `*` in the path.

## Rules

- `tginfo` commands are read-only.
- Do not run `setup-app` or database-mutating commands as routine inspection.
- Loading application code can execute project-defined import, startup, and request-hook code.
- Application logs go to stderr; the listing goes to stdout. Treat any nonzero exit as failure.
- Database info is `{enabled, orm}` only; auth is `{enabled}` only. No credentials are exposed.

## Workflow

1. `tginfo summary` to understand the project.
2. `tginfo routes` to find the controller/action you need.
3. `tginfo models` or `tginfo templates` for specific resources.
4. `tginfo scaffolds` before creating new conventional structure.
5. `python -m pytest --collect-only -q` to discover tests without running them.
6. `tgshell` for runtime/WebTest checks.
