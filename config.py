#coding=utf-8
from __future__ import absolute_import

DEBUG = False
PORT = 5000
AUTO_INDEX = True

ENABLE_CACHE = True

SITE_TITLE = "TEST"
BASE_URL = "/"
SITE_AUTHOR = "DTynn"
SITE_DESCRIPTION = "for test"

POST_DATE_FORMAT = "%Y/%M/%d"

IGNORE_FILES = ["index.md"]

THEME_NAME = "default"
PLUGINS = ["pagination"]

# for pagination plugin
PAGINATION_LIMIT = 10