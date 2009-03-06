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
                    'repoze.what-quickstart >= 1.0'
                    ]

install_requirements = [
                        'TurboGears2>=2.0b5',
                        'sqlalchemy-migrate>=0.4.4',
                        'SQLAlchemy>=0.5',
                        'repoze.what-quickstart >= 1.0',
                        'repoze.who >= 1.0.10'
                        ]

setup(
    name='tg.devtools',
    version="2.0b7",
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
