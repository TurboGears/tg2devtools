import os 
import sys

def extend_parser(parser):
    parser.add_option(
            '--trunk',
            dest='trunk',
            action='store_true',
            default=False,
            help='Install TurboGears in development mode, useful for when you want to contribute back patches (experimental, requires pip)')
    parser.add_option(
            '--requirements',
            dest='requirement_file',
            metavar='requirements.txt',
            default=None,
            help='URL or path to the pip requirement files to use')
    parser.add_option(
            '--pip',
            dest='use_pip',
            action='store_true',
            default=False,
            help='Use pip instead of easy_install (experimental)')

def after_install(options, home_dir):
    if sys.platform == 'win32':
        bin = "Scripts"
    else:
        bin = "bin"

    pip = os.path.join(home_dir,bin,'pip')
    easy_install = os.path.join(home_dir,bin,'easy_install')

    if options.requirement_file:
        print "Sorry option not supported yet"
        return

    def execute(cmd,params):
        cmd = cmd + ' ' + params
        print "Running command...."
        print cmd
        subprocess.call(cmd.split())

    print "Installing turbogears...."
    if options.use_pip:
        execute(easy_install,'pip')
        if options.trunk:
            execute(pip,'install -e svn+http://svn.turbogears.org/trunk')
            execute(pip,'install -e svn+http://svn.turbogears.org/projects/tg.devtools/trunk')
        else:
            execute(pip,'install -i http://www.turbogears.org/2.0/downloads/current/index tg.devtools')
    else:#use easy_install
        execute(easy_install,'-i http://www.turbogears.org/2.0/downloads/current/index tg.devtools')


