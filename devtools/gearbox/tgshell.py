from __future__ import print_function

import os, sys, tg

from cliff.command import Command
from paste.deploy import loadapp
from webtest import TestApp

class ShellCommand(Command):
    """Opens an interactive shell with a PasteDeploy loadable app loaded

    The optional CONFIG_FILE argument specifies the config file to use for
    the interactive shell. CONFIG_FILE defaults to 'development.ini'.

    This allows you to test your mapper, models, and simulate web requests
    using ``paste.fixture``.

    Example::

        $ gearbox shell my-development.ini

    """
    def get_description(self):
        return "Opens an interactive shell with a TurboGears2 app loaded"

    def get_parser(self, prog_name):
        parser = super(ShellCommand, self).get_parser(prog_name)

        parser.add_argument('-d', '--disable-ipython',
            action='store_true',
            dest='disable_ipython',
            help="Don't use IPython if it is available")

        parser.add_argument("-c", "--config",
            help='application config file to read (default: development.ini)',
            dest='config_file', default="development.ini")

        return parser

    def take_action(self, opts):
        config_file = opts.config_file
        config_name = 'config:%s' % config_file
        here_dir = os.getcwd()
        locs = dict(__name__="tgshell")

        # Load locals and populate with objects for use in shell
        sys.path.insert(0, here_dir)

        # Load the wsgi app first so that everything is initialized right
        wsgiapp = loadapp(config_name, relative_to=here_dir)
        test_app = TestApp(wsgiapp)

        # Make available the tg.request and other global variables
        tresponse = test_app.get('/_test_vars')

        pkg_name = tg.config['package_name']

        # Start the rest of our imports now that the app is loaded
        model_module = pkg_name + '.model'
        helpers_module = pkg_name + '.lib.helpers'
        base_module = pkg_name + '.lib.base'

        if self._can_import(model_module):
            locs['model'] = sys.modules[model_module]

        if self._can_import(helpers_module):
            locs['h'] = sys.modules[helpers_module]

        exec ('import tg') in locs
        exec ('from tg import app_globals, config, request, response, '
              'session, tmpl_context, url') in locs
        locs.pop('__builtins__', None)

        # Import all objects from the base module
        __import__(base_module)

        base = sys.modules[base_module]
        base_public = [__name for __name in dir(base) if not\
                                                         __name.startswith('_') or __name == '_']
        locs.update((name, getattr(base, name)) for name in base_public)
        locs.update(dict(wsgiapp=wsgiapp, app=test_app))

        mapper = tresponse.config.get('routes.map')
        if mapper:
            locs['mapper'] = mapper

        banner = "  All objects from %s are available\n" % base_module
        banner += "  Additional Objects:\n"
        if mapper:
            banner += "  %-10s -  %s\n" % ('mapper', 'Routes mapper object')
        banner += "  %-10s -  %s\n" % ('wsgiapp',
                                       "This project's WSGI App instance")
        banner += "  %-10s -  %s\n" % ('app',
                                       'WebTest.TestApp wrapped around wsgiapp')

        try:
            if opts.disable_ipython:
                raise ImportError()

            # try to use IPython if possible
            try:
                # ipython >= 0.11
                from IPython.frontend.terminal.embed import InteractiveShellEmbed
                shell = InteractiveShellEmbed(banner2=banner)
            except ImportError:
                # ipython < 0.11
                from IPython.Shell import IPShellEmbed
                shell = IPShellEmbed()
                shell.set_banner(shell.IP.BANNER + '\n\n' + banner)

            shell(local_ns=locs, global_ns={})
        except ImportError:
            import code
            py_prefix = sys.platform.startswith('java') and 'J' or 'P'
            newbanner = "TurboGears2 Interactive Shell\n%sython %s\n\n" %\
                        (py_prefix, sys.version)
            banner = newbanner + banner
            shell = code.InteractiveConsole(locals=locs)
            try:
                import readline
            except ImportError:
                pass
            
            shell.interact(banner)

    def _can_import(self, name):
        try:
            __import__(name)
            return True
        except ImportError:
            return False
