---
name: tg-shell
description: Use when you need to run Python code in a fully loaded TurboGears application context for runtime checks, debugging, or WebTest requests. Use gearbox tgshell to get an interactive shell with the app loaded.
---

# TurboGears Runtime Shell

You are working with a TurboGears project and need to execute code in the fully loaded application context. Use `gearbox tgshell` for runtime checks, debugging, and WebTest requests.

## When to use this skill

Use this skill when you need to:
- Run Python code in the fully loaded application context
- Perform runtime checks that require the app to be loaded
- Make WebTest requests to test application behavior
- Debug issues that only manifest at runtime
- Inspect application state, configuration, or services

Do **not** use this skill for:
- Static project inspection (use `tg-inspect` instead)
- Creating conventional project files (use `tg-scaffold` instead)
- Running database migrations or setup-app as routine inspection

## Available commands

All commands should be run from the **TurboGears project root directory** in the project's normal environment.

### Interactive shell

Launch an interactive Python shell with the application loaded:

```bash
gearbox tgshell -c development.ini
```

The `-c` / `--config` option specifies the application configuration file (defaults to `development.ini`).

### Running scripts

Execute a Python script in the loaded application context:

```bash
gearbox tgshell -c development.ini your_script.py
```

### WebTest requests

Use WebTest to make requests against the loaded application:

```python
# `app` is provided by tgshell as a WebTest TestApp when WebTest is installed.

# Make a GET request
response = app.get('/')
print(response.status_int)
print(response.text)

# Make a POST request with form data
response = app.post('/login', {'username': 'admin', 'password': 'secret'})

# Check response
assert 'Welcome' in response.text
```

### Common WebTest patterns

```python
# Follow redirects
response = app.get('/login', status=302)
response = response.follow()

# Check status codes
assert response.status_int == 200

# Check response content
assert 'Expected Content' in response.text

# Check headers
assert response.content_type == 'text/html'

# Form submission
form = response.forms['login-form']
form['username'] = 'test'
form['password'] = 'test'
response = form.submit()

# JSON APIs
response = app.get('/api/users', status=200)
data = response.json

# File uploads
response = app.post('/upload', upload_files=[('file', 'content.txt', b'file content')])
```

### TurboGears request context

The application provides a request context manager for testing:

```python
from tg import request, response, config

# Within tgshell, you can use the context manager
with request.context('/'):
    # request and response objects are available
    print(request.path)
    print(response.status)
    
    # Access config
    print(config.get('sqlalchemy.url'))
```

## Safety rules

- `gearbox tgshell` loads the application but **does not run setup-app, migrations, or database writes** as part of inspection
- Runtime debugging belongs in `tgshell`, not in static inspection tools
- Use WebTest for programmatic requests, not for browser-driven testing
- Do not run `setup-app`, migrations, or other database-mutating commands unless the user explicitly asks for that kind of work
- Be explicit about which configuration file you're using

## Workflow

1. Start with `tg-inspect` for static analysis
2. Use `gearbox tgshell -c development.ini` when you need runtime access
3. Import the application's models, controllers, or services as needed
4. Use WebTest to make requests and verify behavior
5. Use the TurboGears request context manager when you need request/response objects
