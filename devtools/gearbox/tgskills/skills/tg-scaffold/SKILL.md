---
name: tg-scaffold
description: Use when creating new TurboGears models, controllers, templates, or other conventional project files. Use gearbox scaffold to create framework-conventional structure, then edit generated code directly.
---

# TurboGears Project Scaffolding

Use `uv run gearbox scaffold` to generate conventional structure from the
project's scaffold templates, then edit the generated files directly.

## Commands

Discover available scaffolds first:

    uv run gearbox tginfo scaffolds

Create one or more items for a target:

    uv run gearbox scaffold model photo
    uv run gearbox scaffold controller blog
    uv run gearbox scaffold model controller template article

The last form creates `model/article.py`, `controllers/article.py`, and
`templates/article.xhtml` in one pass. Add `controller_test` to also generate a
WebTest functional test. Prefer single scaffolds for targeted additions.

Common options: `--subdir`, `--lookup`, `--path`, `--no-package`.

## After scaffolding

1. Import the model from the model package if it should be exported.
2. Mount page controllers in `RootController`; API controllers in `APIController`.
3. Expose templates from a controller action if they should be reachable.
4. If models changed and migrations apply, generate a revision with
   `uv run gearbox migrate autogenerate <name> -c development.ini` and review it.
5. Edit the generated code directly to add specific behavior.

## Rules

- Scaffolding writes project files; review generated code before relying on it.
- Do not run `setup-app` or apply migrations unless explicitly asked.
- For runtime debugging of scaffolded code, use `tgshell` with WebTest requests.
