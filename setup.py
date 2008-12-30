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
                    'repoze.what >= 1.0rc1'
                    ]

setup(
    name='tg.devtools',
    version="2.0b2",
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
    install_requires=[
        'Catwalk',
        'sprox',
        'BeautifulSoup',
        'FormEncode>=1.2',
        'Paste>=1.7',
        'PEAK-Rules',
        'repoze.tm2',
        'repoze.what',
        'repoze.who>=1.0.8',
        'sqlalchemy-migrate>=0.4.4',
        'SQLAlchemy>=0.5.0beta3',
        'SQLAlchemy>=0.5beta3',
        'ToscaWidgets>=0.9',
        'TurboGears2',
        'TurboJson',
        'tw.forms>=0.9.2',
        'WebTest',
        'wsgiref==0.1.2',
        'zope.sqlalchemy',

        'Pylons>=0.9.7beta5',
    ],
    entry_points='''
        [paste.global_paster_command]
        quickstart = devtools.commands.quickstart:QuickstartCommand
        [paste.paster_command]
        crud = devtools.commands.crud:CrudCommand
        migrate = devtools.commands.migration:MigrateCommand
        [turbogears2.command]
        quickstart = devtools.commands.quickstart:QuickstartCommand
        crud = devtools.commands.crud:CrudCommand
        migrate = devtools.commands.migration:MigrateCommand
        [paste.paster_create_template]
        turbogears2=devtools.pastetemplate:TurboGearsTemplate
        [turbogears2.template]
        turbogears2=devtools.pastetemplate:TurboGearsTemplate
    ''',
    test_suite='nose.collector',
    tests_require = test_requirements,
)
