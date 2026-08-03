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
- Running database migrations or setup-app

## Available commands

All commands should be run from the **TurboGears project root directory** in the project's normal environment so `gearbox` can import the application correctly.

### Project summary

Get factual project basics including package name, renderers, paths, root controller, database state, and auth state:

```bash
gearbox tginfo summary --json
```

Use `--json` for machine-readable output that agents can parse reliably.

### Routes and actions

Inspect the static TurboGears object-dispatch route map:

```bash
gearbox tginfo routes --json
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
gearbox tginfo models --json
```

Includes name, fully-qualified class/module, source, ORM kind (sqlalchemy/ming/unknown), and docstring.

### Templates

Inventory recognized template files:

```bash
gearbox tginfo templates --json
```

Includes template dotted name, file path, renderer/engine, and `exposed_by` list of route paths that expose each template.

### Scaffolds

Discover available Gearbox scaffold templates:

```bash
gearbox tginfo scaffolds --json
```

## Safety rules

- These commands are **read-only** - they do not modify the project
- Do not run `setup-app`, migrations, or database-mutating commands as part of routine inspection
- Loading application code can trigger global module execution like any Python import
- Source locations in output are relative to the project root for easy navigation
- Index paths: RootController.index is `/`, subcontroller index is `/subcontroller/`
- Dynamic dispatch: `_lookup` and exposed `_default` appear as synthetic flat route rows with `*` in the path

## Workflow

1. Start with `gearbox tginfo summary --json` to understand the project
2. Use `gearbox tginfo routes --json` to find the controller/action you need
3. Use `gearbox tginfo models --json` or `gearbox tginfo templates --json` for specific resources
4. Use `gearbox tginfo scaffolds --json` before creating new conventional structure
