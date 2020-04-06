#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from django.conf.urls import patterns, url  # pragma: no cover


urlpatterns = patterns(  # pragma: no cover
    "",
    url("^$", 'viewfunc', name='root-of-app'),
)
