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
gearbox tginfo summary --project . --config development.ini --json
```

Use `--json` for machine-readable output that agents can parse reliably.

The summary reports the capability facts needed for workflow selection:
database (enabled/ORM), auth, renderers, and root controller. Combine with
`gearbox tginfo scaffolds --json` and `gearbox migrate --help` for the full
capability picture (generators, migration subcommands).

### Routes and actions

Inspect the static TurboGears object-dispatch route map:

```bash
gearbox tginfo routes --project . --config development.ini --json
```

This returns flat route/action rows with:
- path
- kind (controller, action, dynamic_lookup, dynamic_default)
- controller fully-qualified name and source location
- action name and source location
- controller and action docstrings
- params, controller_allow_only, action_requires, validations
- exposures (renderer, content type, template, resolved template file)

### Models

List models exported by the project model package:

```bash
gearbox tginfo models --project . --config development.ini --json
```

Includes name, fully-qualified class/module, source, ORM kind (sqlalchemy/ming/unknown), and docstring.

### Templates

Inventory recognized template files:

```bash
gearbox tginfo templates --project . --config development.ini --json
```

Includes template dotted name, file path, renderer/engine, and `exposed_by` list of route paths that expose each template.

### Scaffolds

Discover available Gearbox scaffold templates:

```bash
gearbox tginfo scaffolds --project . --config development.ini --json
```

## Safety rules

- These `tginfo` commands are **read-only** - they do not modify the project.
- Do not run `setup-app`, migration upgrades, or other database-mutating commands as part of routine inspection.
- For a read-only migration status check, use `gearbox migrate -c development.ini db_version` only.
- Loading application code can execute project-defined import, startup, and request-hook code, like any Python import. This applies to both `tginfo` and `tgshell`.
- Source locations in output are relative to the project root for easy navigation.
- Index paths: RootController.index is `/`, subcontroller index is `/subcontroller/`.
- Dynamic dispatch: `_lookup` and exposed `_default` appear as synthetic flat route rows with `*` in the path.

## Output contract

- `--json` writes a single JSON document to **stdout**; application import/startup log lines go to **stderr**. Parse stdout directly without filtering.
- Exit codes: `0` success; `1` missing subcommand; `2` unknown subcommand or not run inside the project; `4` config file load failure. Treat any nonzero exit as failure and do not trust partial output.
- Output never contains credentials: database info is `{enabled, orm}` only (no URL), auth is `{enabled}` only. No redaction step is needed.
- JSON keys are sorted and rows are deterministically ordered; output is byte-stable across runs for the same project.

## Workflow

1. Start with `gearbox tginfo summary --project . --config development.ini --json` to understand the project.
2. Use `gearbox tginfo routes --project . --config development.ini --json` to find the controller/action you need.
3. Use `gearbox tginfo models --project . --config development.ini --json` or `gearbox tginfo templates --project . --config development.ini --json` for specific resources.
4. Use `gearbox tginfo scaffolds --project . --config development.ini --json` before creating new conventional structure.
5. Run `python -m pytest --collect-only -q` to discover tests without executing them.
6. For runtime checks or WebTest requests, use `gearbox tgshell -c development.ini` in the fully loaded application context.
