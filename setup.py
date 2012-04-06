# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import sys, os

test_requirements = ['coverage',
                    'nose',
                    'repoze.tm2 >= 1.0a5',
                    'TurboKid >= 1.0.4',
                    'TurboJson >= 1.3',
                    'zope.sqlalchemy >= 0.4',
                    'SQLAlchemy >= 0.5',
                    'repoze.what-quickstart >= 1.0.3',
                    'Babel >=0.9.4',
                    'tgext.admin>=0.3.9',
                    ]

install_requirements = [
                        'TurboGears2 >= 2.1.5',
                        ]

setup(
    name='tg.devtools',
    version="2.1.5",
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
        turbogears2-minimal=devtools.pastetemplate:TurboGearsMinimalTemplate
        tgext=devtools.pastetemplate:TurboGearsExtTemplate
        [turbogears2.template]
        turbogears2=devtools.pastetemplate:TurboGearsTemplate
    ''',
    test_suite='nose.collector',
    tests_require = test_requirements,
    dependency_links=[
        "http://www.turbogears.org/2.1/downloads/current/"
        ]
)
