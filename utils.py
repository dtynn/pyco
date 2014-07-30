#coding=utf-8
from __future__ import absolute_import
from flask import current_app, g
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


def run_hook(hook_name):
    for plugin_module in g.plugins:
        func = plugin_module.__dict__.get(hook_name)
        if callable(func):
            func()
    return


def load_config(app, config_name="config.py"):
    app.config.from_pyfile(config_name)
    app.config.setdefault("AUTO_INDEX", True)
    app.config.setdefault("HOST", None)
    app.config.setdefault("PORT", None)
    app.config.setdefault("DEBUG", False)
    app.config.setdefault("ENABLE_CACHE", True)
    app.config.setdefault("SITE_TITLE", "Pyco Site")
    app.config.setdefault("BASE_URL", "/")
    app.config.setdefault("SITE_AUTHOR", "")
    app.config.setdefault("SITE_DESCRIPTION", "description")
    app.config.setdefault("PLUGINS", [])
    app.config.setdefault("NOT_FOUND_FILE", "404")
    app.config.setdefault("SITE_INDEX_FILE", "index")
    app.config.setdefault("POST_DATE_FORMAT", "%Y/%M/%d")
    app.config.setdefault("IGNORE_FILES", [])
    app.config.setdefault("THEME_NAME", "default")
    return