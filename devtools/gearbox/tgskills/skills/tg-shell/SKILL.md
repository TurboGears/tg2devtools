---
name: tg-shell
description: Use when you need to run Python code in a fully loaded TurboGears application context for runtime checks, debugging, or WebTest requests. Use gearbox tgshell to get an interactive shell with the app loaded.
---

# TurboGears Runtime Shell

Use `gearbox tgshell` from an installed TurboGears project root for runtime
checks. Pass an explicit configuration; use `test.ini` with an in-memory
quickstart database for isolated checks.

## Prerequisite

WebTest recipes require the generated project's testing extra:

```bash
python -m pip install -e '.[testing]'
```

## Run a script

```bash
gearbox tgshell -c test.ini debug.py
```

Omit `debug.py` for an interactive session. `tgshell` makes `wsgiapp` and
TurboGears globals including `config` and `request` available. It provides
`model` only when the application has an importable `<package>.model` module.
It provides `app` only when WebTest is installed; `app` is a WebTest `TestApp`
around `wsgiapp`.

`tgshell` loads the configured WSGI app, then immediately requests
`/_test_vars`. That may run project imports, application startup, middleware,
and request hooks. `tgshell` itself does not run `setup-app`, migrations, or
intentional database writes.

## Inspect locals and make a fake HTTP request

This recipe requires WebTest because it uses `app`.

```python
print("locals:", wsgiapp)
print("app:", app)
print("package:", config["package_name"])

response = app.get("/", status=302)
print("HTTP status:", response.status_int)

from tg.util.webtest import test_context
with test_context(app, "/"):
    assert request.path == "/"
    print("request path:", request.path)
```

Use `test_context` only when code needs a separately scoped fake request. Do
not use TurboGears' old request context manager.

## SQLAlchemy quickstart only

This deliberately creates a temporary `TodoItem`, flushes it, and rolls the
transaction back. It leaves no record behind. Replace `TodoItem` for a project
that uses a different SQLAlchemy model.

```python
TodoItem = model.TodoItem
print(model.DBSession.query(TodoItem).all())

temporary = TodoItem(title="tgshell temporary item")
model.DBSession.add(temporary)
model.DBSession.flush()
temporary_id = temporary.id
assert model.DBSession.query(TodoItem).filter_by(id=temporary_id).one() is temporary

model.DBSession.rollback()
assert model.DBSession.query(TodoItem).filter_by(id=temporary_id).first() is None
print("SQLAlchemy cleanup complete")
```

## Ming quickstart only

This deliberately creates a temporary `TodoItem`, flushes it, then deletes
that exact object and clears the Ming session. It leaves no record behind.
Replace `TodoItem` for a project that uses a different Ming model.

```python
TodoItem = model.TodoItem
print(TodoItem.query.find({}).all())

temporary = TodoItem(title="tgshell temporary item")
model.DBSession.flush()
temporary_id = temporary._id
assert TodoItem.query.find({"_id": temporary_id}).all() == [temporary]

temporary.delete()
model.DBSession.flush()
model.DBSession.clear()
assert TodoItem.query.find({"_id": temporary_id}).all() == []
print("Ming cleanup complete")
```

## Safety rules

- Use `tg-inspect` for static inspection; use `tgshell` for loaded-runtime checks.
- Do not run `setup-app`, migrations, or other database-mutating commands
  unless changing that environment is intentional.
- The in-memory `test.ini` database is process-local. Its schema may need test
  setup; that setup is not a normal debugging step.
