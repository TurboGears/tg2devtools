# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import sys, os

test_requirements = ['coverage',
                    'nose',
                    'repoze.tm2',
                    'TurboKid',
                    'TurboJson',
                    'zope.sqlalchemy',
                    'SQLAlchemy>=0.5beta3',
                    'repoze.what-quickstart'
                    ]
                    
install_requirements = ['Pylons>=0.9.7beta5',
                        'Catwalk',
                        'TurboGears2>=2.0b3',

                        'sprox',
                        'BeautifulSoup',
                        'Beaker>=1.1.3',
                        'FormEncode>=1.2',
                        'Paste>=1.7',
                        'PEAK-Rules',
                        'repoze.tm2',
                        'repoze.what-quickstart',
                        'repoze.who >= 1.0.10',
                        'Routes>=1.10.2',
                        'sqlalchemy-migrate>=0.4.4',
                        'SQLAlchemy>=0.5.0beta3',
                        'SQLAlchemy>=0.5beta3',
                        'ToscaWidgets>=0.9',
                        'TurboJson',
                        'tgext.crud',
                        'tw.forms>=0.9.2',
                        'WebTest',
                        'WebOb',
                        'wsgiref==0.1.2',
                        'zope.sqlalchemy',
                    ]

if sys.version_info[:2] == (2,4):
   install_requires += ["pysqlite"]

setup(
    name='tg.devtools',
    version="2.0b5",
    description="",
    long_description="""""",
    classifiers=[],
    keywords='turbogears',
    author="TurboGears Team 2008",
    author_email="turbogears@groups.google.com",
    url="www.turbogears.org",
    license="MIT",
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires = install_requirements,
    entry_points='''
        [paste.global_paster_command]
        quickstart = devtools.commands.quickstart:QuickstartCommand
        [paste.paster_command]
        migrate = devtools.commands.migration:MigrateCommand
        [turbogears2.command]
        quickstart = devtools.commands.quickstart:QuickstartCommand
        migrate = devtools.commands.migration:MigrateCommand
        [paste.paster_create_template]
        turbogears2=devtools.pastetemplate:TurboGearsTemplate
        [turbogears2.template]
        turbogears2=devtools.pastetemplate:TurboGearsTemplate
    ''',
    test_suite='nose.collector',
    tests_require = test_requirements,
)
