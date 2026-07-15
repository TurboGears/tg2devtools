---
name: tg-scaffold
description: Use when creating new TurboGears models, controllers, templates, or other conventional project files. Use gearbox scaffold to create framework-conventional structure, then edit generated code directly.
---

# TurboGears Project Scaffolding

You are working with a TurboGears project and need to create conventional project files. Use the `gearbox scaffold` command to generate framework-conventional structure from the project's scaffold templates, then edit the generated code directly.

## When to use this skill

Use this skill when you need to create:
- New models
- New controllers
- New templates
- Other conventional TurboGears project structure

Do **not** use this skill for:
- Runtime request debugging (use `tg-shell` instead)
- Inspecting existing project structure (use `tg-inspect` instead)
- Running database migrations or setup-app

## Available commands

All commands should be run from the **TurboGears project root directory** in the project's normal environment so `gearbox` can import the application correctly.

### Create conventional files

Generate one or more scaffold items:

```bash
gearbox scaffold <scaffold-name> <target> [options]
```

Common scaffold names include: `model`, `controller`, `template`, `crud`, `quickstart`

Example - create a Photo model:
```bash
gearbox scaffold model photo
```

Example - create a Blog controller:
```bash
gearbox scaffold controller blog
```

### Discover available scaffolds

First, check what scaffolds are available in this project:

```bash
gearbox tginfo scaffolds --json
```

This shows the scaffold templates discovered by Gearbox, including template path, relative directory, and output extension.

### Common options

- `--lookup` or `-l`: Lookup template
- `--path` or `-p`: Path for template lookup
- `--subdir`: Subdirectory for output
- `--no-package`: Disable package creation
- `--dry-run`: Show what would be created without writing files
- `--json`: Output in JSON format

Example with options:
```bash
gearbox scaffold controller admin --subdir controllers --dry-run
```

## Next steps after scaffolding

After using `gearbox scaffold`:

1. **Models**: Import the model from the model package if it should be exported. Create/review migrations manually if needed.
2. **Controllers**: Mount the controller in RootController if a URL is desired.
3. **Templates**: Expose the template from a controller action if it should be reachable.
4. **Edit directly**: The scaffold generates conventional structure - edit the generated files directly to add your specific logic.

## Safety rules

- `gearbox scaffold` uses Gearbox scaffold semantics - do not invent different overwrite or safety behavior
- Scaffolding writes project files - review generated code before relying on it
- Do not run `setup-app` or migrations unless explicitly asked
- For runtime debugging of scaffolded code, use `tg-shell` with WebTest requests

## Workflow

1. Use `gearbox tginfo scaffolds --json` to discover available scaffold templates
2. Use `gearbox scaffold <name> <target> --dry-run --json` to preview what will be created
3. Run `gearbox scaffold <name> <target>` to create the files
4. Edit the generated code directly to add your specific behavior
5. Use `tg-inspect` to verify the new structure appears correctly
