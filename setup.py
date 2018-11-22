#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
from io import open
import re
import sys
import subprocess
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('litecli/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))


def open_file(filename):
    """Open and read the file *filename*."""
    with open(filename) as f:
        return f.read()


readme = open_file('README.md')

install_requirements = [
    'click >= 4.1',
    'Pygments >= 1.6',
    'prompt_toolkit>=2.0.0,<2.1.0',
    'sqlparse>=0.2.2,<0.3.0',
    'configobj >= 5.0.5',
    'cryptography >= 1.0.0',
    'cli_helpers[styles] >= 1.0.1',
]

class test(TestCommand):

    user_options = [('pytest-args=', 'a', 'Arguments to pass to pytest')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        unit_test_errno = subprocess.call(
            'pytest ' + self.pytest_args,
            shell=True
        )
        # cli_errno = subprocess.call('behave test/features', shell=True)
        # sys.exit(unit_test_errno or cli_errno)
        sys.exit(unit_test_errno)

setup(
    name='litecli',
    author='dbcli',
    author_email='thomas@roten.us',
    version=version,
    url='https://github.com/dbcli/litecli',
    packages=find_packages(),
    package_data={'litecli': ['liteclirc', 'AUTHORS', 'SPONSORS']},
    description='CLI for SQLite Databases with auto-completion and syntax '
                'highlighting.',
    long_description=readme,
    install_requires=install_requirements,
    cmdclass={'test': test},
    entry_points={
        'console_scripts': ['litecli = litecli.main:cli'],
        'distutils.commands': [
            'lint = tasks:lint',
            # 'test = tasks:test',
        ],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: SQL',
        'Topic :: Database',
        'Topic :: Database :: Front-Ends',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
