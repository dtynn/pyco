#coding=utf-8
from __future__ import absolute_import
from flask import current_app, g, make_response
from types import ModuleType


def load_plugins():
    loaded_plugins = []
    plugins = current_app.config.get("PLUGINS")
    for module_or_module_name in plugins:
        if type(module_or_module_name) is ModuleType:
            loaded_plugins.append(module_or_module_name)
        elif isinstance(module_or_module_name, basestring):
            try:
                module = __import__(module_or_module_name)
            except ImportError:
                continue
            loaded_plugins.append(module)
    g.plugins = loaded_plugins
    return


def load_config(app, config_name="config.py"):
    app.config.from_pyfile(config_name)
    app.config.setdefault("AUTO_INDEX", True)
    app.config.setdefault("DEBUG", False)
    app.config.setdefault("SITE_INDEX_URL", "/")
    app.config.setdefault("SITE_TITLE", "Pyco Site")
    app.config.setdefault("BASE_URL", "/")
    app.config.setdefault("SITE_AUTHOR", "")
    app.config.setdefault("SITE_DESCRIPTION", "description")
    app.config.setdefault("PLUGINS", [])
    app.config.setdefault("IGNORE_FILES", [])
    app.config.setdefault("THEME_NAME", "default")
    return


def make_content_response(output, status_code, etag=None):
    response = make_response(output, status_code)
    response.cache_control.public = "public"
    response.cache_control.max_age = 600
    if etag is not None:
        response.set_etag(etag)
    return response