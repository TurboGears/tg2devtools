# -*- coding: UTF-8 -*-

from setuptools import setup, find_packages
import sys, os

setup(
    name='tg.devtools',
    version="1.9.7a2",
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
    install_requires=['Pylons>=0.9.7beta5','TurboGears2', 
        'SQLAlchemy', 'PEAK-Rules',
        'sqlalchemy-migrate>=0.4.4', 'ToscaWidgets>=0.9', 
        'tw.forms>=0.9', 'DBSprockets >=0.5dev-r380',
        'tg.ext.repoze.who', 'TurboJson>=1.2',
        'wsgiref==0.1.2',
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
)
