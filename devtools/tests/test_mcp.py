import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs
from urllib.request import Request, urlopen

from tg import config, expose, milestones, validate
from tg.controllers import RestController, TGController
from tg.validation import Convert

from devtools.gearbox.mcp import GearboxMCPHTTPServer, GearboxMCPStdioServer, TurboGearsMCPTools


def json_decoration(validations=None, before_validate=None):
    return SimpleNamespace(
        exposed=True,
        engines={"application/json": ("json", "", [], {})},
        custom_engines={},
        validations=validations or [],
        hooks={"before_validate": before_validate or []},
    )


def html_decoration():
    return SimpleNamespace(
        exposed=True,
        engines={"text/html": ("kajiki", "template", [], {})},
        custom_engines={},
    )


class JsonRootController(TGController):
    def exposed(self, name: str, count: int = 1):
        """Create the named thing."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def html(self):
        raise AssertionError("Non-json actions should not be listed")


JsonRootController.exposed.decoration = json_decoration()


class HtmlFormRootController(TGController):
    def json_action(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def page(self):
        raise AssertionError("HTML actions should not be listed")

    def form(self):
        raise AssertionError("HTML form actions should not be listed")


HtmlFormRootController.json_action.decoration = json_decoration()
HtmlFormRootController.page.decoration = html_decoration()
HtmlFormRootController.form.decoration = html_decoration()


class JsonAdminController(TGController):
    def create(self, enabled: bool):
        """Create an admin object."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")


JsonAdminController.create.decoration = json_decoration()
JsonRootController.admin = JsonAdminController()


class ValidationRootController(TGController):
    def custom(self, name: str):
        raise AssertionError("Unsupported validation actions should not be listed")

    def form(self, name: str):
        raise AssertionError("Unsupported validation actions should not be listed")

    def generated(self, name: str, count: int = 1):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def typed(self, name: str, count: int = 1):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def validator(self, name: str):
        raise AssertionError("Unsupported validation actions should not be listed")


ValidationRootController.custom.decoration = json_decoration(before_validate=[lambda *args: None])
ValidationRootController.form.decoration = json_decoration(validations=[SimpleNamespace(validators=object())])
ValidationRootController.generated.decoration = json_decoration(
    validations=[SimpleNamespace(generated_from_signature=True, validators={"name": object()})]
)
ValidationRootController.typed.decoration = json_decoration()
ValidationRootController.validator.decoration = json_decoration(
    validations=[SimpleNamespace(validators={"name": object()})]
)


class MixedValidationRootController(TGController):
    def mixed(self, name: str):
        raise AssertionError("Mixed validation provenance actions should not be listed")


MixedValidationRootController.mixed.decoration = json_decoration(
    validations=[
        SimpleNamespace(generated_from_signature=True),
        SimpleNamespace(validators={"name": object()}),
    ]
)


class JsonItemsController(RestController):
    def post(self, name: str):
        """Create an item."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def get_all(self):
        """List items."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def get_one(self, item_id: int):
        """Get one item."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def put(self, item_id: int, name: str):
        """Update an item."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def post_delete(self, item_id: int):
        """Delete an item."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def patch(self, item_id: int, enabled: bool):
        """Patch an item."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")


for method_name in ("post", "get_all", "get_one", "put", "post_delete", "patch"):
    getattr(JsonItemsController, method_name).decoration = json_decoration()


class RestRootController(TGController):
    pass


RestRootController.items = JsonItemsController()


class HtmlFormItemsController(RestController):
    def post(self, name: str):
        raise AssertionError("HTML form actions should not be listed")

    def get_all(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")


HtmlFormItemsController.post.decoration = html_decoration()
HtmlFormItemsController.get_all.decoration = json_decoration()


class HtmlFormRestRootController(TGController):
    pass


HtmlFormRestRootController.items = HtmlFormItemsController()


class ValidationItemsController(RestController):
    def post(self, name: str):
        raise AssertionError("Unsupported validation actions should not be listed")

    def get_all(self, limit: int = 10):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")


ValidationItemsController.post.decoration = json_decoration(
    validations=[SimpleNamespace(validators={"name": object()})]
)
ValidationItemsController.get_all.decoration = json_decoration()


class RestValidationRootController(TGController):
    pass


RestValidationRootController.items = ValidationItemsController()


class DynamicLookupItemsController(RestController):
    def get_all(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def by_slug(self, slug: str):
        raise AssertionError("Dynamic routes must be explicitly declared before listing")

    def _lookup(self, slug, *remainder):
        raise AssertionError("Discovery must not execute dynamic dispatch methods")


for method_name in ("get_all", "by_slug", "_lookup"):
    getattr(DynamicLookupItemsController, method_name).decoration = json_decoration()


class DynamicLookupRootController(TGController):
    pass


DynamicLookupRootController.items = DynamicLookupItemsController()


class DeclaredDynamicItemsController(RestController):
    mcp_dynamic_routes = (
        {"name": "by_slug", "method": "by_slug", "http_method": "GET", "path": "/{slug}"},
    )

    def get_all(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def by_slug(self, slug: str, include: bool = False):
        """Fetch one item by slug."""
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def undeclared(self):
        raise AssertionError("Only mcp_dynamic_routes entries should be listed")

    def _lookup(self, slug, *remainder):
        raise AssertionError("Discovery must not execute dynamic dispatch methods")


for method_name in ("get_all", "by_slug", "undeclared", "_lookup"):
    getattr(DeclaredDynamicItemsController, method_name).decoration = json_decoration()


class DeclaredDynamicRootController(TGController):
    pass


DeclaredDynamicRootController.items = DeclaredDynamicItemsController()


def json_body_app(environ, start_response):
    """WSGI app that echoes request details, parsing JSON body for non-GET."""
    method = environ["REQUEST_METHOD"]
    path = environ["PATH_INFO"]
    query = {name: values[0] for name, values in parse_qs(environ.get("QUERY_STRING") or "").items()}

    content_type = environ.get("CONTENT_TYPE", "")
    data = {}
    if method != "GET" and "application/json" in content_type:
        length = int(environ.get("CONTENT_LENGTH") or "0")
        if length:
            data = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
    elif method != "GET":
        # Fallback for form-encoded (should not occur with decode_json_params=True)
        length = int(environ.get("CONTENT_LENGTH") or "0")
        if length:
            body = environ["wsgi.input"].read(length).decode("utf-8")
            data = {name: values[0] for name, values in parse_qs(body).items()}

    payload = json.dumps(
        {
            "method": method,
            "path": path,
            "query": query,
            "data": data,
        }
    ).encode("utf-8")
    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))])
    return [payload]


class ResponseClassRootController(TGController):
    def json_success(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def validation_failure(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def app_failure(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def non_json_success(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def invalid_json_success(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def redirect(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")

    def cookie(self):
        raise AssertionError("MCP calls must go through WSGI, not controller methods")


for method_name in (
    "json_success",
    "validation_failure",
    "app_failure",
    "non_json_success",
    "invalid_json_success",
    "redirect",
    "cookie",
):
    getattr(ResponseClassRootController, method_name).decoration = json_decoration()


def response_class_app(environ, start_response):
    path = environ["PATH_INFO"]
    if path == "/validation_failure":
        payload = json.dumps({"error": "name is required"}).encode("utf-8")
        start_response("400 Bad Request", [("Content-Type", "application/json")])
        return [payload]
    if path == "/app_failure":
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Traceback (most recent call last):\nsecret internals"]
    if path == "/non_json_success":
        start_response("200 OK", [("Content-Type", "text/html")])
        return [b"<html>not json</html>"]
    if path == "/invalid_json_success":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [b"{"]
    if path == "/redirect":
        start_response("302 Found", [("Location", "/json_success"), ("Set-Cookie", "session=secret")])
        return [b""]
    payload = json.dumps({"ok": True}).encode("utf-8")
    start_response("200 OK", [("Content-Type", "application/json"), ("Set-Cookie", "session=secret")])
    return [payload]


class MCPToolDiscoveryTests(unittest.TestCase):
    def test_json_actions_become_dotted_tools_with_type_hint_schema(self):
        tools = TurboGearsMCPTools(json_body_app, JsonRootController()).list_tools()

        names = [tool["name"] for tool in tools]
        self.assertEqual(names, ["admin.create", "exposed"])
        exposed = next(tool for tool in tools if tool["name"] == "exposed")
        self.assertEqual(exposed["description"], "Create the named thing.")
        self.assertEqual(exposed["inputSchema"]["properties"]["name"], {"type": "string"})
        self.assertEqual(exposed["inputSchema"]["properties"]["count"], {"type": "integer", "default": 1})
        self.assertEqual(exposed["inputSchema"]["required"], ["name"])

    def test_html_and_form_actions_are_warned_and_not_exported_as_tools(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, HtmlFormRootController()).list_tools()

        self.assertEqual([tool["name"] for tool in tools], ["json_action"])
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool form", warnings)
        self.assertIn("Skipping MCP tool page", warnings)
        self.assertIn("only @expose('json') actions are supported", warnings)
        self.assertIn("HTML/form endpoints and MCP Apps are not exported", warnings)

    def test_tool_call_submits_post_with_json_body(self):
        tools = TurboGearsMCPTools(json_body_app, JsonRootController())

        result = tools.call_tool("admin.create", {"enabled": True})

        self.assertFalse(result["isError"])
        # With decode_json_params, POST bodies are JSON objects
        self.assertEqual(
            result["structuredContent"],
            {"method": "POST", "path": "/admin/create", "query": {}, "data": {"enabled": True}},
        )

    def test_actions_with_tg_validation_metadata_are_skipped_unless_generated_from_signature(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, ValidationRootController()).list_tools()

        self.assertEqual([tool["name"] for tool in tools], ["generated", "typed"])
        generated = tools[0]
        self.assertEqual(generated["inputSchema"]["properties"]["name"], {"type": "string"})
        self.assertEqual(generated["inputSchema"]["properties"]["count"], {"type": "integer", "default": 1})
        self.assertEqual(generated["inputSchema"]["required"], ["name"])

        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool custom", warnings)
        self.assertIn("Skipping MCP tool form", warnings)
        self.assertIn("Skipping MCP tool validator", warnings)

    def test_mixed_validation_provenance_is_skipped(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, MixedValidationRootController()).list_tools()

        self.assertEqual(tools, [])
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool mixed", warnings)

    def test_real_tg_validate_metadata_is_skipped_even_for_convert_shape(self):
        config.update(
            {
                "renderers": ["json"],
                "rendering_engines_options": {"json": {"content_type": "application/json"}},
                "rendering_engines_without_vars": ["json"],
            }
        )

        class RealValidationRootController(TGController):
            @expose("json")
            @validate({"name": Convert(str, "Invalid")})
            def explicit_convert(self, name: str):
                raise AssertionError("Unsupported validation actions should not be listed")

            @expose("json")
            @validate()
            def typed(self, name: str, count: int = 1):
                raise AssertionError("MCP calls must go through WSGI, not controller methods")

        milestones.renderers_ready.reach()

        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, RealValidationRootController()).list_tools()

        self.assertEqual(tools, [])
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool explicit_convert", warnings)
        self.assertIn("Skipping MCP tool typed", warnings)

    def test_rest_controller_actions_become_semantic_tools(self):
        tools = TurboGearsMCPTools(json_body_app, RestRootController()).list_tools()

        names = [tool["name"] for tool in tools]
        self.assertEqual(
            names,
            [
                "items.create",
                "items.get_all",
                "items.get_one",
                "items.update",
                "items.delete",
                "items.patch",
            ],
        )
        get_one = next(tool for tool in tools if tool["name"] == "items.get_one")
        self.assertEqual(get_one["description"], "Get one item.")
        self.assertEqual(get_one["inputSchema"]["properties"]["item_id"], {"type": "integer"})
        self.assertEqual(get_one["inputSchema"]["required"], ["item_id"])

    def test_rest_controller_html_form_actions_are_warned_and_not_exported_as_tools(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, HtmlFormRestRootController()).list_tools()

        self.assertEqual([tool["name"] for tool in tools], ["items.get_all"])
        self.assertNotIn("items.create", [tool["name"] for tool in tools])
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool items.create", warnings)
        self.assertIn("only @expose('json') actions are supported", warnings)

    def test_rest_controller_validation_metadata_is_skipped_from_tools_list(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, RestValidationRootController())

        server = GearboxMCPStdioServer(tools)
        response = server.handle_message('{"jsonrpc":"2.0","id":1,"method":"tools/list"}')

        listed_tools = response["result"]["tools"]
        names = [tool["name"] for tool in listed_tools]
        self.assertEqual(names, ["items.get_all"])
        self.assertNotIn("items.create", names)
        get_all = listed_tools[0]
        self.assertEqual(get_all["inputSchema"]["properties"]["limit"], {"type": "integer", "default": 10})

        warnings = "\n".join(logs.output)
        self.assertIn("Skipping MCP tool items.create", warnings)

    def test_rest_controller_dynamic_dispatch_is_warned_and_skipped_by_default(self):
        with self.assertLogs("devtools.gearbox.mcp", level="WARNING") as logs:
            tools = TurboGearsMCPTools(json_body_app, DynamicLookupRootController()).list_tools()

        names = [tool["name"] for tool in tools]
        self.assertEqual(names, ["items.get_all"])
        self.assertNotIn("items.by_slug", names)
        warnings = "\n".join(logs.output)
        self.assertIn("Skipping dynamic MCP routes for items", warnings)
        self.assertIn("_lookup", warnings)
        self.assertIn("mcp_dynamic_routes is not declared", warnings)

    def test_rest_controller_dynamic_routes_require_explicit_metadata(self):
        tools = TurboGearsMCPTools(json_body_app, DeclaredDynamicRootController())

        listed_tools = tools.list_tools()
        names = [tool["name"] for tool in listed_tools]
        self.assertEqual(names, ["items.get_all", "items.by_slug"])
        self.assertNotIn("items.undeclared", names)
        by_slug = next(tool for tool in listed_tools if tool["name"] == "items.by_slug")
        self.assertEqual(by_slug["description"], "Fetch one item by slug.")
        self.assertEqual(by_slug["inputSchema"]["properties"]["slug"], {"type": "string"})
        self.assertEqual(by_slug["inputSchema"]["properties"]["include"], {"type": "boolean", "default": False})

        result = tools.call_tool("items.by_slug", {"slug": "first-item", "include": True})

        self.assertFalse(result["isError"])
        self.assertEqual(
            result["structuredContent"],
            {"method": "GET", "path": "/items/first-item", "query": {"include": "True"}, "data": {}},
        )

    def test_rest_controller_tools_submit_real_http_methods_and_paths(self):
        tools = TurboGearsMCPTools(json_body_app, RestRootController())

        create = tools.call_tool("items.create", {"name": "first"})
        get_one = tools.call_tool("items.get_one", {"item_id": 7, "verbose": True})
        update = tools.call_tool("items.update", {"item_id": 7, "name": "changed"})
        delete = tools.call_tool("items.delete", {"item_id": 7})
        patch = tools.call_tool("items.patch", {"item_id": 7, "enabled": False})

        # JSON body for POST/PUT/PATCH/DELETE
        self.assertEqual(
            create["structuredContent"],
            {"method": "POST", "path": "/items", "query": {}, "data": {"name": "first"}},
        )
        # GET uses query string; urlencode renders True as "True"
        self.assertEqual(
            get_one["structuredContent"],
            {"method": "GET", "path": "/items/7", "query": {"verbose": "True"}, "data": {}},
        )
        self.assertEqual(
            update["structuredContent"],
            {"method": "PUT", "path": "/items/7", "query": {}, "data": {"name": "changed"}},
        )
        self.assertEqual(
            delete["structuredContent"],
            {"method": "DELETE", "path": "/items/7", "query": {}, "data": {}},
        )
        self.assertEqual(
            patch["structuredContent"],
            {"method": "PATCH", "path": "/items/7", "query": {}, "data": {"enabled": False}},
        )

    def test_json_body_preserves_native_types(self):
        """JSON body submission preserves bool/int types rather than stringifying."""
        tools = TurboGearsMCPTools(json_body_app, JsonRootController())

        result = tools.call_tool("admin.create", {"enabled": True, "count": 42})

        self.assertFalse(result["isError"])
        data = result["structuredContent"]["data"]
        self.assertIs(data["enabled"], True)
        self.assertEqual(data["count"], 42)

    def test_missing_rest_path_argument_returns_validation_tool_error(self):
        def raising_app(environ, start_response):
            raise AssertionError("missing path arguments should not submit to WSGI")

        tools = TurboGearsMCPTools(raising_app, RestRootController())

        result = tools.call_tool("items.get_one", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("Missing required argument: item_id", text)
        self.assertNotIn("application exception", text)

    def test_successful_json_tool_response_exposes_structured_content(self):
        tools = TurboGearsMCPTools(response_class_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"], {"ok": True})
        self.assertEqual(result["content"], [{"type": "text", "text": '{"ok": true}'}])

    def test_quoted_utf8_json_charset_exposes_structured_content(self):
        def quoted_utf8_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", 'application/json; charset="utf-8"')])
            return [b'{"ok": true}']

        tools = TurboGearsMCPTools(quoted_utf8_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"], {"ok": True})

    def test_validation_failure_returns_actionable_tool_error(self):
        tools = TurboGearsMCPTools(response_class_app, ResponseClassRootController())

        result = tools.call_tool("validation_failure", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 400 Bad Request", text)
        self.assertIn("name is required", text)

    def test_non_utf8_error_response_returns_tool_error(self):
        def binary_error_app(environ, start_response):
            start_response("400 Bad Request", [("Content-Type", "application/json")])
            return [b"\xff"]

        tools = TurboGearsMCPTools(binary_error_app, ResponseClassRootController())

        result = tools.call_tool("validation_failure", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 400 Bad Request", text)
        self.assertIn("could not be decoded as text", text)

    def test_large_error_response_body_is_bounded(self):
        def large_error_app(environ, start_response):
            start_response("400 Bad Request", [("Content-Type", "text/plain")])
            return [("x" * 2100).encode("utf-8")]

        tools = TurboGearsMCPTools(large_error_app, ResponseClassRootController())

        result = tools.call_tool("validation_failure", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertLess(len(text), 2100)
        self.assertIn("[truncated]", text)

    def test_application_failure_omits_raw_traceback_from_tool_error(self):
        tools = TurboGearsMCPTools(response_class_app, ResponseClassRootController())

        result = tools.call_tool("app_failure", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 500 Internal Server Error", text)
        self.assertIn("check TurboGears application logs", text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("secret internals", text)

    def test_raised_application_exception_returns_tool_error(self):
        def raising_app(environ, start_response):
            raise RuntimeError("secret internals")

        tools = TurboGearsMCPTools(raising_app, ResponseClassRootController())

        with self.assertLogs("devtools.gearbox.mcp", level="ERROR"):
            result = tools.call_tool("app_failure", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("application exception", text)
        self.assertIn("check TurboGears application logs", text)
        self.assertNotIn("secret internals", text)

    def test_non_json_success_returns_tool_error(self):
        tools = TurboGearsMCPTools(response_class_app, ResponseClassRootController())

        result = tools.call_tool("non_json_success", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Expected a JSON response", text)
        self.assertIn("text/html", text)

    def test_invalid_json_success_returns_tool_error(self):
        tools = TurboGearsMCPTools(response_class_app, ResponseClassRootController())

        result = tools.call_tool("invalid_json_success", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_non_finite_json_success_returns_invalid_json_tool_error(self):
        def non_finite_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b'{"value": NaN}']

        tools = TurboGearsMCPTools(non_finite_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertTrue(result["isError"])
        self.assertNotIn("structuredContent", result)
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_bad_json_charset_returns_invalid_json_tool_error(self):
        def bad_charset_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json; charset=bogus")])
            return [b'{"ok": true}']

        tools = TurboGearsMCPTools(bad_charset_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertTrue(result["isError"])
        self.assertNotIn("structuredContent", result)
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_non_utf_json_charset_returns_invalid_json_tool_error(self):
        def latin1_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json; charset=latin-1")])
            return [b'{"ok": true}']

        tools = TurboGearsMCPTools(latin1_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertTrue(result["isError"])
        self.assertNotIn("structuredContent", result)
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_empty_json_success_returns_invalid_json_tool_error(self):
        def empty_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b""]

        tools = TurboGearsMCPTools(empty_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertTrue(result["isError"])
        self.assertNotIn("structuredContent", result)
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_literal_null_json_success_returns_structured_null(self):
        def null_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b"null"]

        tools = TurboGearsMCPTools(null_json_app, ResponseClassRootController())

        result = tools.call_tool("json_success", {})

        self.assertFalse(result["isError"])
        self.assertIsNone(result["structuredContent"])
        self.assertEqual(result["content"], [{"type": "text", "text": "null"}])

    def test_non_utf8_json_success_returns_invalid_json_tool_error(self):
        def invalid_utf8_json_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b"\xff"]

        tools = TurboGearsMCPTools(invalid_utf8_json_app, ResponseClassRootController())

        result = tools.call_tool("invalid_json_success", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 200 OK", text)
        self.assertIn("Invalid JSON response", text)

    def test_redirect_response_is_not_followed_or_exposed_as_success(self):
        paths = []

        def redirect_app(environ, start_response):
            paths.append(environ["PATH_INFO"])
            if environ["PATH_INFO"] == "/redirect":
                start_response("302 Found", [("Location", "/json_success"), ("Set-Cookie", "session=secret")])
                return [b""]
            payload = json.dumps({"followed": True}).encode("utf-8")
            start_response("200 OK", [("Content-Type", "application/json")])
            return [payload]

        tools = TurboGearsMCPTools(redirect_app, ResponseClassRootController())

        result = tools.call_tool("redirect", {})

        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("HTTP 302 Found", text)
        self.assertIn("Redirect response was not followed", text)
        self.assertIn("Location: /json_success", text)
        self.assertNotIn("session=secret", text)
        self.assertEqual(paths, ["/redirect"])

    def test_response_cookies_are_not_persisted_between_tool_calls(self):
        cookies = []

        def cookie_app(environ, start_response):
            cookies.append(environ.get("HTTP_COOKIE"))
            payload = json.dumps({"cookie": environ.get("HTTP_COOKIE")}).encode("utf-8")
            start_response(
                "200 OK",
                [("Content-Type", "application/json"), ("Set-Cookie", "session=secret")],
            )
            return [payload]

        tools = TurboGearsMCPTools(cookie_app, ResponseClassRootController())

        first = tools.call_tool("cookie", {})
        second = tools.call_tool("cookie", {})

        self.assertFalse(first["isError"])
        self.assertFalse(second["isError"])
        self.assertEqual(first["structuredContent"], {"cookie": None})
        self.assertEqual(second["structuredContent"], {"cookie": None})
        self.assertEqual(cookies, [None, None])


class MCPCommandTests(unittest.TestCase):
    def test_http_transport_uses_http_server_not_stdio(self):
        import devtools.gearbox.mcp as mcp_module

        wsgiapp = object()
        tools = MagicMock()
        opts = SimpleNamespace(
            config_file="development.ini",
            app_name=None,
            transport="http",
            http_host="127.0.0.1",
            http_port=8765,
            http_token=None,
        )
        cmd = mcp_module.MCPCommand(
            app=SimpleNamespace(options=SimpleNamespace(log_file=None)),
            app_args=SimpleNamespace(verbose_level=0),
        )

        with patch.object(mcp_module.logging.root, "handlers", []), \
             patch.object(mcp_module.logging.Logger.manager, "loggerDict", {}), \
             patch.object(mcp_module, "setup_logging"), \
             patch.object(mcp_module, "loadapp", return_value=wsgiapp) as loadapp, \
             patch.object(mcp_module.TurboGearsMCPTools, "from_wsgi_app", return_value=tools) as from_wsgi_app, \
             patch.object(mcp_module.GearboxMCPHTTPServer, "__init__", return_value=None) as http_init, \
             patch.object(mcp_module.GearboxMCPHTTPServer, "serve", return_value=None) as http_serve, \
             patch.object(mcp_module.GearboxMCPStdioServer, "serve") as stdio_serve:
            cmd.take_action(opts)

        loadapp.assert_called_once()
        from_wsgi_app.assert_called_once_with(wsgiapp)
        http_init.assert_called_once_with(tools, host="127.0.0.1", port=8765, token=None)
        http_serve.assert_called_once_with()
        stdio_serve.assert_not_called()

    def test_http_transport_rejects_non_loopback_without_token_before_loading_app(self):
        import devtools.gearbox.mcp as mcp_module

        opts = SimpleNamespace(
            config_file="development.ini",
            app_name=None,
            transport="http",
            http_host="0.0.0.0",
            http_port=8765,
            http_token=None,
        )
        cmd = mcp_module.MCPCommand(
            app=SimpleNamespace(options=SimpleNamespace(log_file=None)),
            app_args=SimpleNamespace(verbose_level=0),
        )

        with patch.object(mcp_module, "loadapp") as loadapp:
            with self.assertRaisesRegex(ValueError, "requires --http-token"):
                cmd.take_action(opts)

        loadapp.assert_not_called()

    def test_http_transport_accepts_non_loopback_with_token(self):
        import devtools.gearbox.mcp as mcp_module

        wsgiapp = object()
        tools = MagicMock()
        opts = SimpleNamespace(
            config_file="development.ini",
            app_name=None,
            transport="http",
            http_host="0.0.0.0",
            http_port=8765,
            http_token="secret",
        )
        cmd = mcp_module.MCPCommand(
            app=SimpleNamespace(options=SimpleNamespace(log_file=None)),
            app_args=SimpleNamespace(verbose_level=0),
        )

        with patch.object(mcp_module.logging.root, "handlers", []), \
             patch.object(mcp_module.logging.Logger.manager, "loggerDict", {}), \
             patch.object(mcp_module, "setup_logging"), \
             patch.object(mcp_module, "loadapp", return_value=wsgiapp), \
             patch.object(mcp_module.TurboGearsMCPTools, "from_wsgi_app", return_value=tools), \
             patch.object(mcp_module.GearboxMCPHTTPServer, "__init__", return_value=None) as http_init, \
             patch.object(mcp_module.GearboxMCPHTTPServer, "serve", return_value=None):
            cmd.take_action(opts)

        http_init.assert_called_once_with(tools, host="0.0.0.0", port=8765, token="secret")

    def test_http_help_and_env_configuration_describe_remote_auth_boundary(self):
        import devtools.gearbox.mcp as mcp_module

        cmd = mcp_module.MCPCommand(
            app=SimpleNamespace(options=SimpleNamespace(log_file=None)),
            app_args=SimpleNamespace(verbose_level=0),
        )
        with patch.dict(
            mcp_module.os.environ,
            {
                "GEARBOX_MCP_HTTP_HOST": "0.0.0.0",
                "GEARBOX_MCP_HTTP_PORT": "9000",
                "GEARBOX_MCP_HTTP_TOKEN": "secret",
            },
        ):
            parser = cmd.get_parser("gearbox mcp")
            opts = parser.parse_args([])

        self.assertEqual(opts.http_host, "0.0.0.0")
        self.assertEqual(opts.http_port, 9000)
        self.assertEqual(opts.http_token, "secret")
        help_text = parser.format_help()
        self.assertIn("ordinary anonymous TG requests", help_text)
        self.assertIn("normal WSGI", help_text)
        self.assertIn("behavior", help_text)


class MCPHTTPServerConstructorTests(unittest.TestCase):
    def test_non_loopback_http_server_requires_token(self):
        with self.assertRaisesRegex(ValueError, "token is required"):
            GearboxMCPHTTPServer(TurboGearsMCPTools(json_body_app, JsonRootController()), host="0.0.0.0", port=0)


class MCPHTTPServerTests(unittest.TestCase):
    def setUp(self):
        self.server = GearboxMCPHTTPServer(TurboGearsMCPTools(json_body_app, JsonRootController()), port=0)
        self.thread = threading.Thread(target=self.server.serve, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)

    def _post(self, message, origin=None, token=None, url=None):
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["Authorization"] = "Bearer %s" % token
        request = Request(url or self.url, data=json.dumps(message).encode("utf-8"), headers=headers, method="POST")
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Type"], "application/json")
            return json.loads(response.read().decode("utf-8"))

    def test_http_transport_handles_initialize_list_and_call(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        initialize = self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        tools_list = self._post(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            origin=f"http://127.0.0.1:{self.server.server_address[1]}",
        )
        call = self._post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "admin.create", "arguments": {"enabled": True}},
            }
        )

        self.assertEqual(initialize["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual([tool["name"] for tool in tools_list["result"]["tools"]], ["admin.create", "exposed"])
        self.assertEqual(
            call["result"]["structuredContent"],
            {"method": "POST", "path": "/admin/create", "query": {}, "data": {"enabled": True}},
        )

    def test_http_transport_rejects_missing_and_incorrect_authorization_when_token_is_configured(self):
        server = GearboxMCPHTTPServer(TurboGearsMCPTools(json_body_app, JsonRootController()), port=0, token="secret")
        thread = threading.Thread(target=server.serve, daemon=True)
        thread.start()
        url = "http://%s:%s/" % server.server_address
        try:
            for token in (None, "wrong", "sécret"):
                with self.subTest(token=token):
                    with self.assertRaises(HTTPError) as error:
                        self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token=token, url=url)

                    self.assertEqual(error.exception.code, 401)

            response = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, token="secret", url=url)
        finally:
            server.shutdown()
            thread.join(timeout=2)

        self.assertEqual([tool["name"] for tool in response["result"]["tools"]], ["admin.create", "exposed"])

    def test_http_transport_rejects_invalid_origin(self):
        for origin in (
            "http://evil.example",
            "http://[::1",
            "http://127.0.0.1:bad",
            "http://evil.example@127.0.0.1",
            "http://127.0.0.1:",
            "http://127.0.0.1/path",
            "http://127.0.0.1?query=1",
            "http://127.0.0.1#fragment",
            "http://127.0.0.1?",
            "http://127.0.0.1#",
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(HTTPError) as error:
                    self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, origin=origin)

                self.assertEqual(error.exception.code, 403)


class MCPStdioServerTests(unittest.TestCase):
    def test_minimal_tools_list_message(self):
        tools = TurboGearsMCPTools(json_body_app, JsonRootController())
        server = GearboxMCPStdioServer(tools)

        response = server.handle_message('{"jsonrpc":"2.0","id":1,"method":"tools/list"}')

        self.assertEqual(response["id"], 1)
        self.assertEqual([tool["name"] for tool in response["result"]["tools"]], ["admin.create", "exposed"])

    def test_tools_call_message_invokes_existing_tool_behavior(self):
        tools = TurboGearsMCPTools(json_body_app, JsonRootController())
        server = GearboxMCPStdioServer(tools)

        response = server.handle_message(
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"admin.create","arguments":{"enabled":true}}}'
        )

        self.assertEqual(response["id"], 1)
        self.assertEqual(
            response["result"]["structuredContent"],
            {"method": "POST", "path": "/admin/create", "query": {}, "data": {"enabled": True}},
        )

    def test_initialize_and_ping_return_json_rpc_results(self):
        server = GearboxMCPStdioServer(SimpleNamespace(list_tools=lambda: []))

        initialize = server.handle_message('{"jsonrpc":"2.0","id":1,"method":"initialize"}')
        ping = server.handle_message('{"jsonrpc":"2.0","id":2,"method":"ping"}')

        self.assertEqual(initialize["id"], 1)
        self.assertEqual(initialize["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(initialize["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(ping, {"jsonrpc": "2.0", "id": 2, "result": {}})

    def test_notifications_are_ignored(self):
        server = GearboxMCPStdioServer(SimpleNamespace(list_tools=lambda: []))

        response = server.handle_message('{"jsonrpc":"2.0","method":"notifications/initialized"}')

        self.assertIsNone(response)

    def test_protocol_errors_are_stable_for_invalid_messages(self):
        server = GearboxMCPStdioServer(SimpleNamespace(list_tools=lambda: []))
        cases = [
            ("{", None, -32700, "Parse error"),
            ("[]", None, -32600, "Invalid Request"),
            ('{"jsonrpc":"1.0","id":1,"method":"tools/list"}', 1, -32600, "Invalid Request"),
            ('{"id":1,"method":"tools/list"}', 1, -32600, "Invalid Request"),
            ('{"jsonrpc":"2.0","id":2}', 2, -32600, "Invalid Request"),
            ('{"jsonrpc":"2.0","id":3,"method":"tools/list","params":[]}', 3, -32602, "Invalid params"),
        ]

        for line, request_id, code, message in cases:
            with self.subTest(line=line):
                response = server.handle_message(line)
                self.assertEqual(
                    response,
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
                )

    def test_unknown_methods_tools_and_app_exceptions_return_stable_errors(self):
        tools = MagicMock()
        tools.has_tool.return_value = False
        server = GearboxMCPStdioServer(tools)

        unknown_method = server.handle_message('{"jsonrpc":"2.0","id":1,"method":"missing"}')
        unknown_tool = server.handle_message(
            '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"missing"}}'
        )
        invalid_arguments = server.handle_message(
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"known","arguments":[]}}'
        )

        tools.has_tool.return_value = True
        tools.call_tool.side_effect = RuntimeError("app exploded")
        app_exception = server.handle_message(
            '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"known","arguments":{}}}'
        )

        self.assertEqual(
            unknown_method,
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found: missing"}},
        )
        self.assertEqual(
            unknown_tool,
            {"jsonrpc": "2.0", "id": 2, "error": {"code": -32602, "message": "Unknown tool: missing"}},
        )
        self.assertEqual(
            invalid_arguments,
            {"jsonrpc": "2.0", "id": 3, "error": {"code": -32602, "message": "Invalid params"}},
        )
        self.assertEqual(
            app_exception,
            {"jsonrpc": "2.0", "id": 4, "error": {"code": -32000, "message": "Internal error"}},
        )

    def test_stdout_remains_clean_during_mcp_command(self):
        """Integration test: verify MCPCommand keeps stdout clean when app config uses stdout logging.
        
        Tests the actual logging setup and redirection flow from MCPCommand.take_action,
        ensuring no logging bytes leak into stdout (which must remain clean for MCP JSON-RPC).
        """
        import io
        import logging
        import sys
        import tempfile
        import os
        from argparse import Namespace
        from unittest.mock import patch, MagicMock

        # Create a temporary config file that logs to stdout
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write("""[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = INFO
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stdout,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(message)s
""")
            config_file = f.name

        try:
            # Capture stdout and stderr
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            original_root_handlers = logging.root.handlers[:]
            original_logger_dict = logging.Logger.manager.loggerDict.copy()
            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()
            
            sys.stdout = captured_stdout
            sys.stderr = captured_stderr
            
            # Reset logging state to ensure clean test
            logging.root.handlers.clear()
            logging.Logger.manager.loggerDict.clear()
            
            try:
                import devtools.gearbox.mcp as mcp_module
                
                # Mock loadapp to return a simple WSGI app
                def mock_loadapp(app_spec, name=None, relative_to=None, global_conf=None):
                    def simple_app(environ, start_response):
                        start_response('200 OK', [('Content-Type', 'text/plain')])
                        return [b'OK']
                    return simple_app
                
                original_loadapp = mcp_module.loadapp
                mcp_module.loadapp = mock_loadapp
                
                # Mock TurboGearsMCPTools.from_wsgi_app to avoid TG config issues
                original_from_wsgi = mcp_module.TurboGearsMCPTools.from_wsgi_app
                mock_tools = MagicMock()
                mcp_module.TurboGearsMCPTools.from_wsgi_app = MagicMock(return_value=mock_tools)
                
                # Mock GearboxMCPStdioServer.serve to prevent blocking
                original_serve = mcp_module.GearboxMCPStdioServer.serve
                serve_called = []
                
                def mock_serve(self, stdin, stdout):
                    serve_called.append(True)
                
                mcp_module.GearboxMCPStdioServer.serve = mock_serve
                
                try:
                    # Create options namespace
                    opts = Namespace(
                        config_file=config_file,
                        app_name=None,
                        transport="stdio",
                    )
                    
                    # Create command instance with required args
                    cmd = mcp_module.MCPCommand(
                        app=SimpleNamespace(options=SimpleNamespace(log_file=None)),
                        app_args=SimpleNamespace(verbose_level=0)
                    )
                    
                    # Run the actual take_action method
                    cmd.take_action(opts)
                    
                    # Now log a test message - it should go to stderr, not stdout
                    root_logger = logging.getLogger()
                    root_logger.info("Test MCP logging message")
                    
                finally:
                    mcp_module.loadapp = original_loadapp
                    mcp_module.TurboGearsMCPTools.from_wsgi_app = original_from_wsgi
                    mcp_module.GearboxMCPStdioServer.serve = original_serve
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                logging.root.handlers[:] = original_root_handlers
                logging.Logger.manager.loggerDict.clear()
                logging.Logger.manager.loggerDict.update(original_logger_dict)
            
            # Verify the command ran and called serve
            self.assertTrue(serve_called)
            
            # Verify the logging message went to stderr, not stdout
            stderr_content = captured_stderr.getvalue()
            stdout_content = captured_stdout.getvalue()
            
            # The test message should be in stderr
            self.assertIn("Test MCP logging message", stderr_content)
            # stdout should be empty (no logging should leak to stdout)
            self.assertEqual(stdout_content, "")
            
        finally:
            os.unlink(config_file)


if __name__ == "__main__":
    unittest.main()
