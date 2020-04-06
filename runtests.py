#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Testcase runner:
copied from http://stackoverflow.com/a/3851333
"""

from __future__ import absolute_import
import os
import sys

import fire
from django.apps import apps
from django.conf import settings
from django.test.utils import get_runner


BASE_DIR = os.path.dirname(__file__)
settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'ENCODING': 'utf-8',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    },
    INSTALLED_APPS=[
        'pb_model',
        'pb_model.tests',
    ],
    USE_TZ = True,
)

apps.populate(settings.INSTALLED_APPS)


def run(path=''):
    tr = get_runner(settings)()
    abs_path = 'pb_model.tests.tests'
    if path:
        abs_path += '.{}'.format(path)
    failures = tr.run_tests([abs_path,])
    if failures:
        sys.exit(bool(failures))


fire.Fire(run)
