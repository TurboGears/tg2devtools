"""Definitions for TurboGears quickstart templates"""
from paste.script import templates
from tempita import paste_script_template_renderer

class TurboGearsTemplate(templates.Template):
    """
    TurboGears 2 default paste template class
    """
    _template_dir = 'templates/turbogears'
    template_renderer = staticmethod(paste_script_template_renderer)
    summary = 'TurboGears 2.1 Standard Quickstart Template'
    egg_plugins = ['PasteScript', 'Pylons', 'TurboGears2', 'tg.devtools']
    vars = [
        templates.var('sqlalchemy', 'use SQLAlchemy as ORM', default=True),
        templates.var('auth', 'use authentication and authorization support', default="sqlalchemy"),
        templates.var('geo', 'Include GIS support (True/False)', default='False'),
        templates.var('mako', 'Include Mako support (True/False)', default='False'),
    ]

    def pre(self, command, output_dir, vars):
        """Called before template is applied."""
        package_logger = vars['package']
        if package_logger == 'root':
            # Rename the app logger in the rare case a project is named 'root'
            package_logger = 'app'
        vars['package_logger'] = package_logger

        template_engine = \
            vars.setdefault('template_engine',
                'genshi')

        if template_engine == 'mako':
            # Support a Babel extractor default for Mako
            vars['babel_templates_extractor'] = \
                "('templates/**.mako', 'mako', None),\n%s#%s" % (' ' * 4,
                                                                 ' ' * 8)
        else:
            vars['babel_templates_extractor'] = ''

        if vars['geo'] == 'True':
            # Add tgext.geo as paster plugin
            vars['egg_plugins'].append('tgext.geo')


class TurboGearsExtTemplate(templates.Template):
    """
		TurboGears 2 extension paster template class
    """

    summary = 'TurboGears 2 extension template'

    _template_dir = 'templates/tgext'
    template_renderer = staticmethod(paste_script_template_renderer)
    egg_plugins = ['TurboGears2', 'Pylons', 'PasteScript', 'tg.devtools']
    required_templates = []
    vars = [
		    templates.var('description', 'Short description of the extension')
    ]

    def pre(self, command, output_dir, vars):
    	# FIXME: for the moment we have to do a copy/paste from the Turbogears
    	# template so that we have defined the variables from setup.py_tmpl
    	# which is very similar to the one found in the Turbogears quickstart
    	# template.
        template_engine = vars.setdefault('template_engine', 'genshi')
        vars['sqlalchemy'] = True
        if template_engine == 'mako':
            # Support a Babel extractor default for Mako
            vars['babel_templates_extractor'] = \
                "('templates/**.mako', 'mako', None),\n%s#%s" % (' ' * 4,
                                                                 ' ' * 8)
        else:
        	vars['babel_templates_extractor'] = ''
