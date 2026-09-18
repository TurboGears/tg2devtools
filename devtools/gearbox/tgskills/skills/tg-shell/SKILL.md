---
name: tg-shell
description: Use when you need to run Python code in a fully loaded TurboGears application context for runtime checks, debugging, or WebTest requests. Use gearbox tgshell to get an interactive shell with the app loaded.
---

# TurboGears Runtime Shell

Use `uv run gearbox tgshell -c test.ini` from the project root for runtime
checks. `test.ini` uses an in-memory quickstart database for isolated checks.

The positional argument is a script filename, not stdin. Do not pipe code to
`tgshell` or use `-`; write a temporary file:

    cat > /tmp/tg-check.py <<'PY'
    print("package:", config["package_name"])
    print("app:", wsgiapp)
    PY
    uv run gearbox tgshell -c test.ini /tmp/tg-check.py

`tgshell` already provides `wsgiapp`, `config`, `request`, and other TurboGears
globals after the app is loaded. Do not call `loadapp` again. It provides
`model` only when the app has an importable `<package>.model` module, and `app`
(a WebTest `TestApp`) only when WebTest is installed. Omit the filename for an
interactive session.

## WebTest request

Requires WebTest (`app`):

```python
response = app.get("/", status=302)
print("HTTP status:", response.status_int)

from tg.util.webtest import test_context
with test_context(app, "/"):
    assert request.path == "/"
    print("request path:", request.path)
```

Use `test_context` only when code needs a separately scoped fake request.

## SQLAlchemy: temporary record (rolls back)

```python
TodoItem = model.TodoItem
temporary = TodoItem(title="tgshell temporary item")
model.DBSession.add(temporary)
model.DBSession.flush()
temporary_id = temporary.id
assert model.DBSession.query(TodoItem).filter_by(id=temporary_id).one() is temporary
model.DBSession.rollback()
assert model.DBSession.query(TodoItem).filter_by(id=temporary_id).first() is None
```

Replace `TodoItem` with a project model. The record is never committed.

## Rules

- Use `tg-inspect` for static inspection; `tgshell` for loaded-runtime checks.
- Do not run `setup-app`, migrations, or other database-mutating commands unless changing that environment is intentional.
- The in-memory `test.ini` database is process-local; its schema may need test setup, which is not a normal debugging step.
