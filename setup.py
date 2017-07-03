# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import sys, os

test_requirements = [
    'nose',
    'virtualenv == 1.10',
    'kajiki',
    'genshi',
    'jinja2',
    'mako'
]

install_requirements = [
    'TurboGears2 >= 2.3.11',
    'gearbox >= 0.1.1',
    'backlash >= 0.0.7',
    'WebTest<2.0',
    'tgext.debugbar'
]

setup(
    name='tg.devtools',
    version="2.3.10",
    description="",
    long_description="""""",
    classifiers=[],
    keywords='turbogears',
    author="TurboGears Team 2008-2015",
    author_email="turbogears@groups.google.com",
    url="http://www.turbogears.org",
    license="MIT",
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires = install_requirements,
    entry_points={
        'gearbox.commands': [
            'quickstart = devtools.gearbox.quickstart:QuickstartCommand',
            'tgext = devtools.gearbox.tgext:MakeTGExtCommand',
            ],
        'gearbox.project_commands': [
            'sqla-migrate = devtools.gearbox.sqlamigrate:MigrateCommand',
            'migrate = devtools.gearbox.alembic_migrate:MigrateCommand',
            'tgshell = devtools.gearbox.tgshell:ShellCommand',
        ],
    },
    test_suite='nose.collector',
    tests_require = test_requirements,
)
