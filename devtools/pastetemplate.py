"""Definitions for TurboGears quickstart templates"""
from paste.script import templates
from tempita import paste_script_template_renderer

class TurboGearsTemplate(templates.Template):
    """
    TurboGears 2 default paste template class
    """
    _template_dir = 'templates/turbogears'
    template_renderer = staticmethod(paste_script_template_renderer)
    summary = 'TurboGears 2.0 Standard Quickstart Template'
    egg_plugins = ['PasteScript', 'Pylons', 'TurboGears2', 'tg.devtools']
    vars = [
        templates.var('sqlalchemy', 'use SQLAlchemy as ORM', default=True),
        templates.var('auth', 'use authentication and authorization support', default="sqlalchemy"),
        templates.var('geo', 'Include GIS support (True/False)', default='False'),
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

