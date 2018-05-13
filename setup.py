#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
from io import open
import re

from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('litecli/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))


def open_file(filename):
    """Open and read the file *filename*."""
    with open(filename) as f:
        return f.read()


readme = open_file('README.rst')

setup(
    name='litecli',
    author='dbcli',
    author_email='thomas@roten.us',
    version=version,
    url='https://github.com/dbcli/litecli',
    description='CLI for SQLite Databases with auto-completion and syntax '
                'highlighting.',
    long_description=readme,
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
