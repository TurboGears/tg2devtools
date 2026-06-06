"""Architectural probe for serving TurboGears JSON actions through MCP.

Architectural question: can a Gearbox project command load the same PasteDeploy
WSGI app as `gearbox serve`, discover @expose('json') actions, and submit MCP
tool calls as internal HTTP requests without inventing a parallel controller API?
"""

import hmac
import inspect
import ipaddress
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import get_args, get_origin
from urllib.parse import quote, urlencode, urlsplit

import tg
from gearbox.command import Command
from gearbox.utils.log import setup_logging
from paste.deploy import loadapp
from tg.controllers import RestController, TGController


LOGGER = logging.getLogger(__name__)


MCP_HTTP_HOST_ENV = "GEARBOX_MCP_HTTP_HOST"
MCP_HTTP_PORT_ENV = "GEARBOX_MCP_HTTP_PORT"
MCP_HTTP_TOKEN_ENV = "GEARBOX_MCP_HTTP_TOKEN"
MCP_TOOL_ERROR_BODY_LIMIT = 2000


class MCPCommand(Command):
    """Serve TurboGears JSON actions as local MCP tools."""

    _scheme_re = re.compile(r"^[a-z][a-z]+:", re.I)

    def get_description(self):
        return "Serves @expose('json') TurboGears actions as MCP tools"

    def get_parser(self, prog_name):
        parser = super(MCPCommand, self).get_parser(prog_name)
        parser.add_argument(
            "-c",
            "--config",
            help="application config file to read (default: development.ini)",
            dest="config_file",
            default="development.ini",
        )
        parser.add_argument(
            "-n",
            "--app-name",
            dest="app_name",
            metavar="NAME",
            help="Load the named application (default main)",
        )
        parser.add_argument(
            "--transport",
            choices=("stdio", "http"),
            default="stdio",
            help="MCP transport to serve (default: stdio)",
        )
        parser.add_argument(
            "--http-host",
            default=os.environ.get(MCP_HTTP_HOST_ENV, "127.0.0.1"),
            help="HTTP bind address for --transport http (default: %s or 127.0.0.1)" % MCP_HTTP_HOST_ENV,
        )
        parser.add_argument(
            "--http-port",
            type=int,
            default=os.environ.get(MCP_HTTP_PORT_ENV, "8765"),
            help="HTTP port for --transport http (default: %s or 8765)" % MCP_HTTP_PORT_ENV,
        )
        parser.add_argument(
            "--http-token",
            default=os.environ.get(MCP_HTTP_TOKEN_ENV),
            help=(
                "Bearer token for --transport http; required for non-loopback hosts. "
                "This only authorizes MCP HTTP clients: MCP calls still run as ordinary anonymous "
                "TG requests unless the app authenticates them through normal WSGI behavior. "
                "Can also be set with %s."
            ) % MCP_HTTP_TOKEN_ENV,
        )
        return parser

    def take_action(self, opts):
        http_host = getattr(opts, "http_host", "127.0.0.1")
        http_port = getattr(opts, "http_port", 8765)
        http_token = getattr(opts, "http_token", None) or None
        if opts.transport == "http" and not _is_loopback_http_host(http_host) and not http_token:
            raise ValueError(
                "gearbox mcp --transport http requires --http-token or %s when binding to non-loopback host %s"
                % (MCP_HTTP_TOKEN_ENV, http_host)
            )

        app_spec = opts.config_file
        if not self._scheme_re.search(app_spec):
            app_spec = "config:" + app_spec

        # Apply logging config from the application config file, matching gearbox serve behavior.
        # Must be done BEFORE loadapp() to prevent PasteDeploy from creating duplicate handlers.
        log_fn = app_spec
        if log_fn.startswith("config:"):
            log_fn = log_fn[len("config:") :]
        elif log_fn.startswith("egg:"):
            log_fn = None
        if log_fn:
            log_fn = os.path.join(os.getcwd(), log_fn)
            setup_logging(log_fn)

        # Force decode_json_params=True so MCP tool arguments map naturally to TG params.
        # This is passed via global_conf so the TGApp picks it up during initialization.
        # Requires TurboGears2 >= 2.5.1 which supports decode_json_params.
        wsgiapp = loadapp(
            app_spec,
            name=opts.app_name,
            relative_to=os.getcwd(),
            global_conf={"decode_json_params": "true"},
        )

        # Redirect stdout logging handlers to stderr to prevent leaks into MCP stdio stream.
        # This catches handlers created by both setup_logging() and loadapp().
        # Check both named loggers and the root logger.
        # Note: Dynamic handlers created after this point will not be redirected.
        # This is acceptable as TG/PasteDeploy typically create all handlers during init.
        for name in list(logging.Logger.manager.loggerDict.keys()):
            logger = logging.getLogger(name)
            for handler in logger.handlers[:]:
                if handler.stream is sys.stdout:
                    handler.stream = sys.stderr
        for handler in logging.root.handlers[:]:
            if handler.stream is sys.stdout:
                handler.stream = sys.stderr

        tools = TurboGearsMCPTools.from_wsgi_app(wsgiapp)
        if opts.transport == "http":
            GearboxMCPHTTPServer(tools, host=http_host, port=http_port, token=http_token).serve()
        else:
            GearboxMCPStdioServer(tools).serve(sys.stdin, sys.stdout)


class TurboGearsMCPTools:
    """Discovers JSON-exposed TG actions and invokes them through WSGI submissions.

    HTML/form endpoints and MCP Apps are intentionally unsupported by this tools-only server.
    """

    def __init__(self, wsgiapp, root_controller):
        self._wsgiapp = wsgiapp
        self._root_controller = root_controller
        self._tools = self._discover_tools(root_controller)
        self._tools_by_name = {tool.name: tool for tool in self._tools}

    @classmethod
    def from_wsgi_app(cls, wsgiapp):
        # tg.config is available after loadapp, so we can use TGApp.lookup_controller
        # to get the root controller without unwrapping middleware.
        from tg.wsgiapp import TGApp

        root_controller = TGApp.lookup_controller(tg.config, "root")
        if inspect.isclass(root_controller):
            root_controller = root_controller()
        return cls(wsgiapp, root_controller)

    def list_tools(self):
        return [tool.as_mcp_tool() for tool in self._tools]

    def call_tool(self, name, arguments):
        tool = self._tools_by_name[name]
        arguments = arguments or {}
        for path_parameter in tool.path_parameters:
            if path_parameter not in arguments:
                return self._tool_error_result("Missing required argument: %s" % path_parameter)
        try:
            response = self._request_turbogears_tool(tool, arguments)
        except Exception:
            LOGGER.exception("MCP tool %s failed during WSGI submission", name)
            return self._tool_error_result(
                "TurboGears tool raised an application exception; check TurboGears application logs."
            )
        return self._response_as_tool_result(response)

    def has_tool(self, name):
        return name in self._tools_by_name

    def _discover_tools(self, root_controller):
        discovered = []

        def walk(controller, prefix):
            if isinstance(controller, RestController):
                discovered.extend(self._discover_rest_tools(controller, prefix))
                return

            for name in sorted(dir(controller)):
                if name.startswith("_"):
                    continue
                try:
                    value = getattr(controller, name)
                except Exception:
                    continue

                path_segments = list(prefix) if name == "index" else list(prefix) + [name]
                tool_name = ".".join(path_segments) if path_segments else "index"
                if self._is_json_action(value):
                    unsupported_reason = self._unsupported_validation_reason(value)
                    if unsupported_reason:
                        LOGGER.warning("Skipping MCP tool %s: %s", tool_name, unsupported_reason)
                        continue

                    path = "/" + "/".join(path_segments)
                    discovered.append(
                        TurboGearsMCPTool(
                            name=tool_name,
                            http_method="POST",
                            path=path,
                            description=inspect.getdoc(value) or "TurboGears JSON action at %s" % path,
                            input_schema=self._input_schema_for(value),
                        )
                    )
                    continue

                if self._warn_unsupported_exposed_action(tool_name, value):
                    continue

                if isinstance(value, (TGController, RestController)):
                    # Object dispatch makes subcontrollers the natural boundary for
                    # URL-like tool names: /admin/create becomes admin.create.
                    walk(value, list(prefix) + [name])

        walk(root_controller, [])
        return discovered

    def _discover_rest_tools(self, controller, prefix):
        # RestController actions are named by resource semantics, while execution
        # still goes through the real HTTP method and URL that TG dispatches.
        rest_actions = (
            ("create", "POST", "post", ()),
            ("get_all", "GET", "get_all", ()),
            ("get_one", "GET", "get_one", ("first_required",)),
            ("update", "PUT", "put", ("first_required",)),
            ("delete", "DELETE", "post_delete", ("first_required",)),
            ("delete", "DELETE", "delete", ("first_required",)),
            ("patch", "PATCH", "patch", ("first_required",)),
        )
        discovered = []
        used_names = set()
        base_tool_name = ".".join(prefix)
        base_path = "/" + "/".join(prefix)
        controller_name = base_tool_name or type(controller).__name__

        for tool_suffix, http_method, method_name, path_parameter_rule in rest_actions:
            if tool_suffix in used_names:
                continue
            method = getattr(controller, method_name, None)
            tool_name = "%s.%s" % (base_tool_name, tool_suffix) if base_tool_name else tool_suffix
            if not self._is_json_action(method):
                self._warn_unsupported_exposed_action(tool_name, method)
                continue

            unsupported_reason = self._unsupported_validation_reason(method)
            if unsupported_reason:
                LOGGER.warning("Skipping MCP tool %s: %s", tool_name, unsupported_reason)
                continue

            path_parameters = self._rest_path_parameters(method, path_parameter_rule)
            path = base_path or "/"
            if path_parameters:
                path += "/" + "/".join("{%s}" % name for name in path_parameters)

            discovered.append(
                TurboGearsMCPTool(
                    name=tool_name,
                    http_method=http_method,
                    path=base_path or "/",
                    path_parameters=path_parameters,
                    description=inspect.getdoc(method) or "%s %s" % (http_method, path),
                    input_schema=self._input_schema_for(method),
                )
            )
            used_names.add(tool_suffix)

        # Dynamic dispatch cannot be inferred safely; only this metadata hook opts routes in.
        dynamic_routes = getattr(controller, "mcp_dynamic_routes", ()) or ()
        dynamic_methods = []
        for method_name in ("_lookup", "_default", "_dispatch"):
            if method_name in getattr(controller, "__dict__", {}):
                dynamic_methods.append(method_name)
                continue
            for cls in type(controller).__mro__:
                if cls is RestController:
                    break
                if method_name in cls.__dict__:
                    dynamic_methods.append(method_name)
                    break

        if dynamic_methods and not dynamic_routes:
            LOGGER.warning(
                "Skipping dynamic MCP routes for %s: %s present but mcp_dynamic_routes is not declared",
                controller_name,
                ", ".join(dynamic_methods),
            )

        for route in dynamic_routes:
            try:
                route_name = route["name"]
                method = getattr(controller, route["method"], None)
                http_method = route["http_method"].upper()
                route_path = route["path"]
            except (AttributeError, KeyError, TypeError):
                LOGGER.warning("Skipping dynamic MCP route for %s: invalid mcp_dynamic_routes entry", controller_name)
                continue
            if not isinstance(route_name, str) or not isinstance(route_path, str):
                LOGGER.warning("Skipping dynamic MCP route for %s: invalid mcp_dynamic_routes entry", controller_name)
                continue

            tool_name = "%s.%s" % (base_tool_name, route_name) if base_tool_name else route_name
            if route_name in used_names:
                LOGGER.warning("Skipping MCP tool %s: dynamic route conflicts with RestController action", tool_name)
                continue
            if not self._is_json_action(method):
                if not self._warn_unsupported_exposed_action(tool_name, method):
                    LOGGER.warning("Skipping MCP tool %s: dynamic route method is not exposed as JSON", tool_name)
                continue
            unsupported_reason = self._unsupported_validation_reason(method)
            if unsupported_reason:
                LOGGER.warning("Skipping MCP tool %s: %s", tool_name, unsupported_reason)
                continue

            if not route_path.startswith("/"):
                route_path = "/" + route_path
            path = (base_path if base_path != "/" else "") + route_path
            path_parameters = tuple(dict.fromkeys(re.findall(r"{([A-Za-z_][A-Za-z0-9_]*)}", path)))
            discovered.append(
                TurboGearsMCPTool(
                    name=tool_name,
                    http_method=http_method,
                    path=path,
                    path_parameters=path_parameters,
                    description=inspect.getdoc(method) or "%s %s" % (http_method, path),
                    input_schema=self._input_schema_for(method),
                )
            )
            used_names.add(route_name)

        return discovered

    def _is_json_action(self, value):
        if not self._is_exposed_action(value):
            return False

        decoration = getattr(value, "decoration", None)

        for content_type, engine in getattr(decoration, "engines", {}).items():
            renderer = engine[0]
            if renderer == "json" or "json" in content_type:
                return True

        for engine in getattr(decoration, "custom_engines", {}).values():
            content_type, renderer = engine[0], engine[1]
            if renderer == "json" or "json" in content_type:
                return True

        return False

    def _is_exposed_action(self, value):
        decoration = getattr(value, "decoration", None) if inspect.ismethod(value) else None
        return bool(decoration is not None and getattr(decoration, "exposed", False))

    def _warn_unsupported_exposed_action(self, tool_name, value):
        if not self._is_exposed_action(value):
            return False
        LOGGER.warning(
            "Skipping MCP tool %s: only @expose('json') actions are supported by MCP tools; "
            "HTML/form endpoints and MCP Apps are not exported",
            tool_name,
        )
        return True

    def _unsupported_validation_reason(self, method):
        decoration = getattr(method, "decoration", None)
        if decoration is None:
            return None

        validations = getattr(decoration, "validations", None) or []
        if validations and not all(
            getattr(validation, "generated_from_signature", None) is True
            for validation in validations
        ):
            # Only TG's explicit provenance flag distinguishes signature-generated
            # validation from user-authored validators without interpreting validator objects.
            return "TG validation/form metadata cannot be represented from Python type hints"

        hooks = getattr(decoration, "hooks", {}) or {}
        if hooks.get("before_validate"):
            return "TG before_validate hooks cannot be represented from Python type hints"

        return None

    def _input_schema_for(self, method):
        schema = {"type": "object", "properties": {}, "additionalProperties": False}
        required = []

        for name, parameter in inspect.signature(method).parameters.items():
            if name == "self":
                continue
            if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
                continue
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                schema["additionalProperties"] = True
                continue

            param_schema = _json_schema_for_annotation(parameter.annotation)
            if parameter.default is not inspect.Parameter.empty:
                param_schema["default"] = parameter.default
            else:
                required.append(name)
            schema["properties"][name] = param_schema

        if required:
            schema["required"] = required

        return schema

    def _rest_path_parameters(self, method, rule):
        # RestController uses URL shape (not just param names) to select actions.
        # Member actions like get_one(item_id) need the ID in the path:
        # GET /items/7 -> get_one(item_id=7), not GET /items?item_id=7 -> get_all.
        # This helper identifies which parameter should go in the URL path.
        if not rule:
            return ()
        if rule != ("first_required",):
            raise ValueError("Unknown RestController path parameter rule: %r" % (rule,))

        for name, parameter in inspect.signature(method).parameters.items():
            if name == "self":
                continue
            if parameter.kind not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                continue
            if parameter.default is inspect.Parameter.empty:
                return (name,)
        return ()

    def _request_turbogears_tool(self, tool, arguments):
        arguments = dict(arguments)
        url = tool.path

        # REST member and declared dynamic routes need path values in the URL for dispatch.
        for name in tool.path_parameters:
            value = arguments.pop(name)
            placeholder = "{%s}" % name
            if placeholder in url:
                url = url.replace(placeholder, quote(str(value), safe=""))
            else:
                url += "/" + quote(str(value), safe="")

        # For GET, encode remaining args as query string.
        # For non-GET, we will send as JSON body below.
        if tool.http_method == "GET" and arguments:
            url += "?" + urlencode(arguments, doseq=True)

        request = tg.Request.blank(url, method=tool.http_method)
        request.headers["Accept"] = "application/json"

        # Non-GET: send remaining args as JSON body so TG decode_json_params merges into args_params
        if tool.http_method != "GET" and arguments:
            request.body = json.dumps(arguments).encode("utf-8")
            request.content_type = "application/json"

        return request.get_response(self._wsgiapp)

    def _response_as_tool_result(self, response):
        content_type = response.content_type or ""
        if 300 <= response.status_int < 400:
            message = "HTTP %s\nRedirect response was not followed." % response.status
            location = response.headers.get("Location")
            if location:
                message += "\nLocation: %s" % location
            return self._tool_error_result(message)

        if response.status_int < 200 or response.status_int >= 300:
            message = "HTTP %s" % response.status
            if response.status_int >= 500:
                message += "\nResponse body omitted; check TurboGears application logs."
                return self._tool_error_result(message)

            try:
                text = response.text
            except (LookupError, UnicodeError):
                message += "\nResponse body omitted because it could not be decoded as text."
                return self._tool_error_result(message)
            if "json" in content_type:
                try:
                    if text:
                        structured = json.loads(text, parse_constant=_reject_non_finite_json_constant)
                        text = json.dumps(structured, allow_nan=False)
                except ValueError:
                    pass
            elif "html" in content_type:
                text = ""
            if text:
                if len(text) > MCP_TOOL_ERROR_BODY_LIMIT:
                    text = text[:MCP_TOOL_ERROR_BODY_LIMIT] + "\n[truncated]"
                message += "\n%s" % text
            return self._tool_error_result(message)

        if "json" not in content_type:
            return self._tool_error_result(
                "HTTP %s\nExpected a JSON response from the TurboGears tool, got %s."
                % (response.status, content_type or "unknown content type")
            )

        try:
            charset = response.charset
            if charset:
                charset = charset.strip().strip('"\'').strip().lower().replace("_", "-")
                if charset not in ("utf-8", "utf8"):
                    raise UnicodeError("JSON response declared a non-UTF charset")
            text = response.body.decode("utf-8")
            structured = json.loads(text, parse_constant=_reject_non_finite_json_constant)
            content_text = json.dumps(structured, allow_nan=False)
        except (LookupError, UnicodeError, ValueError):
            return self._tool_error_result("HTTP %s\nInvalid JSON response from the TurboGears tool." % response.status)

        return {
            "content": [{"type": "text", "text": content_text}],
            "structuredContent": structured,
            "isError": False,
        }

    def _tool_error_result(self, message):
        return {"content": [{"type": "text", "text": message}], "isError": True}


class GearboxMCPJsonRPCHandler:
    """Local JSON-RPC boundary shared by MCP transports."""

    protocol_version = "2025-11-25"

    def __init__(self, tools):
        self._tools = tools

    def handle_message(self, line):
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return self._error(None, -32700, "Parse error")

        if not isinstance(message, dict):
            return self._error(None, -32600, "Invalid Request")
        if "id" not in message:
            return None

        request_id = message["id"]
        method = message.get("method")
        params = message.get("params")
        if params is None:
            params = {}
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "Invalid params")

        try:
            if method == "initialize":
                return self._result(
                    request_id,
                    {
                        "protocolVersion": self.protocol_version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "gearbox-mcp", "version": "0.1"},
                    },
                )
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                return self._result(request_id, {"tools": self._tools.list_tools()})
            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments")
                if arguments is None:
                    arguments = {}
                if not isinstance(arguments, dict):
                    return self._error(request_id, -32602, "Invalid params")
                if not self._tools.has_tool(name):
                    return self._error(request_id, -32602, "Unknown tool: %s" % name)
                return self._result(request_id, self._tools.call_tool(name, arguments))
        except Exception:
            return self._error(request_id, -32000, "Internal error")

        return self._error(request_id, -32601, "Method not found: %s" % method)

    def _result(self, request_id, result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class GearboxMCPStdioServer:
    """Minimal stdio JSON-RPC server for the discovered TurboGears MCP tools."""

    protocol_version = GearboxMCPJsonRPCHandler.protocol_version

    def __init__(self, tools):
        self._jsonrpc = GearboxMCPJsonRPCHandler(tools)

    def serve(self, stdin, stdout):
        for line in stdin:
            if not line.strip():
                continue
            response = self.handle_message(line)
            if response is not None:
                stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                stdout.flush()

    def handle_message(self, line):
        return self._jsonrpc.handle_message(line)


class GearboxMCPHTTPServer:
    """Small local HTTP JSON-RPC endpoint for the discovered TurboGears MCP tools."""

    protocol_version = GearboxMCPJsonRPCHandler.protocol_version

    def __init__(self, tools, host="127.0.0.1", port=8765, token=None):
        if not _is_loopback_http_host(host) and not token:
            raise ValueError(
                "gearbox mcp HTTP token is required when binding to non-loopback host %s" % host
            )
        self._jsonrpc = GearboxMCPJsonRPCHandler(tools)
        self._token = token or None

        outer = self

        class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                outer._handle_post(self)

            def do_GET(self):
                self.send_error(405, "Method Not Allowed")

            def log_message(self, format, *args):
                LOGGER.debug("MCP HTTP %s", format % args)

        self._httpd = HTTPServer((host, port), MCPHTTPRequestHandler)

    @property
    def server_address(self):
        return self._httpd.server_address

    def serve(self):
        self._httpd.serve_forever()

    def shutdown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def _handle_post(self, request):
        if self._token and not self._has_valid_authorization(request):
            request.send_response(401)
            request.send_header("WWW-Authenticate", "Bearer")
            request.end_headers()
            return

        if request.path != "/":
            request.send_error(404, "Not Found")
            return

        origin = request.headers.get("Origin")
        if origin and not self._is_allowed_origin(origin):
            request.send_error(403, "Forbidden Origin")
            return

        length = int(request.headers.get("Content-Length") or "0")
        body = request.rfile.read(length)
        try:
            line = body.decode("utf-8")
        except UnicodeDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = self._jsonrpc.handle_message(line)

        if response is None:
            request.send_response(204)
            request.end_headers()
            return

        payload = json.dumps(response, separators=(",", ":")).encode("utf-8")
        request.send_response(200)
        request.send_header("Content-Type", "application/json")
        request.send_header("Content-Length", str(len(payload)))
        request.end_headers()
        request.wfile.write(payload)

    def _has_valid_authorization(self, request):
        try:
            return hmac.compare_digest(
                request.headers.get("Authorization") or "",
                "Bearer %s" % self._token,
            )
        except TypeError:
            return False

    def _is_allowed_origin(self, origin):
        try:
            parsed = urlsplit(origin)
            parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme in ("http", "https")
            and parsed.hostname in ("127.0.0.1", "localhost", "::1")
            and parsed.username is None
            and parsed.password is None
            and not parsed.netloc.endswith(":")
            and "?" not in origin
            and "#" not in origin
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        )


@dataclass
class TurboGearsMCPTool:
    name: str
    http_method: str
    path: str
    description: str
    input_schema: dict
    path_parameters: tuple = field(default_factory=tuple)

    def as_mcp_tool(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


JSON_SCHEMA_BY_PYTHON_TYPE = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
}


def _is_loopback_http_host(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _reject_non_finite_json_constant(value):
    raise ValueError("Invalid JSON constant: %s" % value)


def _json_schema_for_annotation(annotation):
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (list, tuple):
        item_schema = _json_schema_for_annotation(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}
    if origin is dict:
        return {"type": "object"}

    schema = JSON_SCHEMA_BY_PYTHON_TYPE.get(annotation)
    if schema is not None:
        return dict(schema)

    return {"type": "string", "description": "Python type hint: %s" % getattr(annotation, "__name__", annotation)}
