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
                    'Babel >=0.9.4',
                    'tgext.admin>=0.3.9',
                    ]

install_requirements = [
                        'TurboGears2 >= 2.3.0dev',
                        'gearbox',
                        'backlash',
                        'WebTest'
                        ]

setup(
    name='tg.devtools',
    version="2.3.0",
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
    entry_points={
        'gearbox.commands': [
            'quickstart = devtools.gearbox.quickstart:QuickstartCommand'
            ],
        'gearbox.project_commands': [
            'sqla-migrate = devtools.gearbox.sqlamigrate:MigrateCommand',
            'migrate = devtools.gearbox.alembic_migrate:MigrateCommand',
            'tgshell = devtools.gearbox.tgshell:ShellCommand'
        ],
    },
    test_suite='nose.collector',
    tests_require = test_requirements,
    dependency_links=[
        "http://tg.gy/230"
        ]
)
