import os 

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

def execute(script,*args):
    print 'Running script'
    print script
    print 20*'-'
    subprocess.Popen(script % locals(),shell=True)

def after_install(options, home_dir):
    print options
    if sys.platform == 'win32':
        activate = "Scripts\\activate.bat"
    else:
        activate = "source bin/activate"

    if options.requirement_file:
        print "Sorry option not supported yet"
        return

    print 'installing turbogears, this will take a while....'
    if options.use_pip:
        if options.trunk:
            install_cmd = """
            pip install -e svn+http://svn.turbogears.org/trunk
            pip install -e svn+http://svn.turbogears.org/projects/tg.devtools/trunk
            """
        else:
            install_cmd = 'pip install -i http://www.turbogears.org/2.0/downloads/current/index tg.devtools'

        execute("""
        cd %(home_dir)s
        %(activate)s
        source %(bin)s/activate
        easy_install pip
        %(install_cmd)s
        """ % locals())
    else:#use easy_install
        execute("""
        cd %(home_dir)s
        %(activate)s
        easy_install -i http://www.turbogears.org/2.0/downloads/current/index tg.devtools
        """ % locals())

