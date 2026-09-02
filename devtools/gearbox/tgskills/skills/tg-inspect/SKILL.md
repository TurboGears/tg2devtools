---
name: tg-inspect
description: Use when inspecting a TurboGears project to discover routes, controllers, models, templates, or project facts. Prefer gearbox tginfo commands over guessing from files.
---

# TurboGears Project Inspection

You are working with a TurboGears project. Use the `gearbox tginfo` command family for structured, reliable inspection of the project.

## When to use this skill

Use this skill when you need to understand:
- Project structure, package name, renderers, and important paths
- Static controller routes, actions, parameters, requirements, validations, and templates
- Models exported by the project model package (SQLAlchemy or Ming)
- Recognized template files and which routes expose them
- Available scaffold templates for creating conventional project structure

Do **not** use this skill for:
- Runtime request debugging (use `tg-shell` instead)
- Creating or modifying project files (use `tg-scaffold` instead)
- Applying database migrations or running setup-app

## Available commands

All commands should be run from the **TurboGears project root directory** in the project's normal environment so `gearbox` can import the application correctly.

Quickstart creates `development.ini` for local development and `test.ini` for
tests; `test.ini` references the development configuration. Quickstart does not
generate `production.ini`, which is deployment-specific. Select the profile
explicitly and do not infer or switch profiles in agent commands.

### Project summary

Get factual project basics including package name, renderers, paths, root controller, database state, and auth state:

```bash
gearbox tginfo summary --project . --config development.ini
```


The summary reports the capability facts needed for workflow selection:
database (enabled/ORM), auth, renderers, and root controller. Combine with
`gearbox tginfo scaffolds` for the full scaffold picture. Migration
support is project-specific; follow the project's generated `AGENTS.md` or
`README.rst` instead of assuming a migration command exists.

### Routes and actions

Inspect the static TurboGears object-dispatch route map:

```bash
gearbox tginfo routes --project . --config development.ini
```

This returns flat route/action rows with:
- path
- kind (controller, action, rest_collection, rest_item, dynamic_lookup, dynamic_default)

For RestController resources, collection methods such as get_all and post are
reported at the collection path, while item methods such as get_one and
post_delete are reported at the item path with a wildcard. These routes are
static descriptions of REST dispatch; use tg-shell for runtime request checks.
- controller fully-qualified name and source location
- action name and source location
- controller and action docstrings
- params, controller_allow_only, action_requires, validations
- exposures (renderer, content type, template, resolved template file)

### Models

List models exported by the project model package:

```bash
gearbox tginfo models --project . --config development.ini
```

Includes name, fully-qualified class/module, source, ORM kind (sqlalchemy/ming/unknown), and docstring.

### Templates

Inventory recognized template files:

```bash
gearbox tginfo templates --project . --config development.ini
```

Includes template dotted name, file path, renderer/engine, and `exposed_by` list of route paths that expose each template.

### Scaffolds

Discover available Gearbox scaffold templates:

```bash
gearbox tginfo scaffolds --project . --config development.ini
```

## Safety rules

- These `tginfo` commands are **read-only** - they do not modify the project.
- Do not run `setup-app` or other database-mutating commands as part of routine inspection.
- Loading application code can execute project-defined import, startup, and request-hook code, like any Python import. This applies to both `tginfo` and `tgshell`.
- Source locations in output are relative to the project root for easy navigation.
- Index paths: RootController.index is `/`, subcontroller index is `/subcontroller/`.
- Dynamic dispatch: `_lookup` and exposed `_default` appear as synthetic flat route rows with `*` in the path.

## Output contract

- Application import and startup log lines go to **stderr**; the route/controller listing goes to **stdout**. Use `--full` to include source paths, docstrings, and parameter metadata for routes. Use `--json` only when you need to parse output programmatically.
- Exit codes: `0` success; `1` missing subcommand; `2` unknown subcommand or not run inside the project; `4` config file load failure. Treat any nonzero exit as failure and do not trust partial output.
- Output never contains credentials: database info is `{enabled, orm}` only (no URL), auth is `{enabled}` only. No redaction step is needed.
- Text output is deterministically ordered and stable across runs for the same project.

## Workflow

1. Start with `gearbox tginfo summary --project . --config development.ini` to understand the project.
2. Use `gearbox tginfo routes --project . --config development.ini` to find the controller/action you need.
3. Use `gearbox tginfo models --project . --config development.ini` or `gearbox tginfo templates --project . --config development.ini` for specific resources.
4. Use `gearbox tginfo scaffolds --project . --config development.ini` before creating new conventional structure.
5. Run `python -m pytest --collect-only -q` to discover tests without executing them.
6. For runtime checks or WebTest requests, use `gearbox tgshell -c development.ini` in the fully loaded application context.
