# -*- coding: UTF-8 -*-

from setuptools import setup, find_packages
import sys, os

setup(
    name='tg.devtools',
    version="1.9.7a1",
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
    install_requires=['Pylons>=0.9.7beta5','TurboGears2==1.9.7a1', 
        'SQLAlchemy>=0.5beta1', 'PEAK-Rules',
        'sqlalchemy-migrate>=0.4.4', 'ToscaWidgets>=0.9', 
        'tw.forms>=0.9', 'DBSprockets >= 0.2, <0.5',
        'tg.ext.repoze.who',
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
