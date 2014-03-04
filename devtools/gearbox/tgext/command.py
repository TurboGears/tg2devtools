from __future__ import print_function

from gearbox.command import TemplateCommand
import re, getpass

class MakeTGExtCommand(TemplateCommand):
    CLEAN_PACKAGE_NAME_RE = re.compile('[^a-zA-Z0-9_]')

    def get_description(self):
        return 'Creates a tgext.* package'

    def get_parser(self, prog_name):
        parser = super(MakeTGExtCommand, self).get_parser(prog_name)

        parser.add_argument('-n', '--name', dest='project',
                            metavar='NAME', required=True,
                            help="Extension Name (without tgext part)")

        parser.add_argument('-a', '--author', dest='author',
                            metavar='AUTHOR',
                            help="Name of the package author")

        parser.add_argument('-e', '--email', dest='author_email',
                            metavar='AUTHOR_EMAIL',
                            help="Email of the package author")

        parser.add_argument('-u', '--url', dest='url',
                            metavar='URL',
                            help="Project homepage")

        parser.add_argument('-l', '--license', dest='license_name',
                            metavar='LICENSE_NAME', default='MIT',
                            help="License used for the project (default: MIT)")

        parser.add_argument('-d', '--description', dest='description',
                            metavar='DESCRIPTION',
                            help="Package description")

        parser.add_argument('-k', '--keywords', dest='keywords',
                            metavar='KEYWORDS', default='turbogears2.extension',
                            help="Package keywords (default: turbogears2.extension)")

        return parser

    def take_action(self, opts):
        opts.project = self.CLEAN_PACKAGE_NAME_RE.sub('', opts.project.lower())
        opts.package = 'tgext.%s' % opts.project
        opts.zip_safe = False
        opts.version = '0.0.1'

        if opts.author is None:
            opts.author = getpass.getuser()

        self.run_template(opts.package, opts)
