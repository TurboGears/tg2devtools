import json
import sys

from gearbox.command import Command

from devtools.gearbox.tginfo_summary import collect_project_summary, format_project_summary


class TgInfoCommand(Command):
    """Inspect TurboGears project facts."""

    def get_description(self):
        return 'Inspect TurboGears project facts'

    def get_parser(self, prog_name):
        parser = super(TgInfoCommand, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(dest='tginfo_command')

        summary = subparsers.add_parser('summary', help='Show factual project summary')
        summary.add_argument('--project', default='.', help='project root directory (default: current directory)')
        summary.add_argument('-c', '--config', dest='config_file', default='development.ini',
                             help='application config file to read (default: development.ini)')
        summary.add_argument('--json', action='store_true', dest='as_json', help='emit JSON output')
        return parser

    def take_action(self, opts):
        if opts.tginfo_command != 'summary':
            raise SystemExit('tginfo requires a subcommand: summary')

        summary = collect_project_summary(project=opts.project, config=opts.config_file)
        if opts.as_json:
            json.dump(summary, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write('\n')
        else:
            sys.stdout.write(format_project_summary(summary))
