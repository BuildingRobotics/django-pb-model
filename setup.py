#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
import os
try:
    from setuptools import find_packages, setup
except ImportError:
    from distutils.core import setup, find_packages


fopen = lambda path: open(os.path.join(os.path.dirname(__file__), path))
with fopen('README.rst') as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-pb-model',
    version='0.1.9.4',
    packages=find_packages(),
    include_package_data=True,
    license='MIT License',
    long_description=README,
    url='https://github.com/myyang/django-pb-model',
    description='Protobuf mixin for Django model',
    author='myyang',
    author_email='ymy1019@gmail.com',
    install_requires=fopen('requirements.txt').read().strip().splitlines(),
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
