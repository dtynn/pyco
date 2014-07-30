#coding=utf-8
from __future__ import absolute_import

PLUGIN_DIR = "plugins/"

THEME_DIR = "theme/"
TEMPLATE_FILE_EXT = ".html"
DEFAULT_INDEX_TMPL_NAME = "index"
DEFAULT_POST_TMPL_NAME = "post"

STATIC_DIR = "static/"
STATIC_BASE_URL = "/static"

CONTENT_DIR = "content/"
CONTENT_FILE_EXT = ".md"
CONTENT_DEFAULT_FILENAME = "index"
CONTENT_NOT_FOUND_FILENAME = "404"

CACHE_DIR = "cache/"
CACHE_FILE_EXT = ".cache"

CHARSET = "utf8"

import sys
sys.path.insert(0, PLUGIN_DIR)

from flask import Flask, current_app, request, abort, render_template, g, make_response, send_file
from flask.views import MethodView
import os
import re
from utils import load_config, load_plugins, make_content_response
from collections import defaultdict
import markdown
from hashlib import sha1


class BaseView(MethodView):
    # common funcs
    def get_file_path(self, url):
        base_path = os.path.join(CONTENT_DIR, url[1:]).rstrip("/")

        file_name = "{}{}".format(base_path, CONTENT_FILE_EXT)
        if self.check_file_exists(file_name):
            return file_name

        file_name = os.path.join(base_path, "{}{}".format(CONTENT_DEFAULT_FILENAME, CONTENT_FILE_EXT))
        if self.check_file_exists(file_name):
            return file_name
        return None

    @staticmethod
    def check_file_exists(file_full_path):
        return os.path.isfile(file_full_path)

    # content
    @property
    def content_not_found_relative_path(self):
        return "{}{}".format(CONTENT_NOT_FOUND_FILENAME, CONTENT_FILE_EXT)

    @property
    def content_not_found_full_path(self):
        return os.path.join(CONTENT_DIR, self.content_not_found_relative_path)

    @property
    def content_ignore_files(self):
        base_files = [self.content_not_found_relative_path]
        base_files.extend(current_app.config.get("IGNORE_FILES"))
        return base_files

    @staticmethod
    def content_splitter(file_content):
        pattern = r"(\n)*/\*(\n)*(?P<meta>(.*\n)*)\*/(?P<content>(.*(\n)?)*)"
        re_pattern = re.compile(pattern)
        m = re_pattern.match(file_content)
        if m is None:
            return "", ""
        return m.group("meta"), m.group("content")

    def parse_file_meta(self, meta_string):
        headers = dict()
        self.run_hook("before_read_file_meta")
        for line in meta_string.split("\n"):
            kv_pair = line.split(":", 1)
            if len(kv_pair) == 2:
                headers[kv_pair[0].lower()] = kv_pair[1].strip()
        return headers

    @staticmethod
    def parse_content(content_string):
        return markdown.markdown(content_string, extensions=["fenced_code", "codehilite"])

    # cache
    @staticmethod
    def generate_etag(content_file_full_path):
        file_stat = os.stat(content_file_full_path)
        base = "{mtime:0.0f}_{size:d}_{fpath}".format(mtime=file_stat.st_mtime, size=file_stat.st_size,
                                                      fpath=content_file_full_path)
        return sha1(base).hexdigest()

    def get_cache_file_path(self, content_file_full_path):
        cache_path = os.path.join(CACHE_DIR,
                                  "{}{}".format(self.generate_etag(content_file_full_path), CACHE_FILE_EXT))
        return cache_path

    def check_cache(self, content_file_full_path):
        cache_path = self.get_cache_file_path(content_file_full_path)
        return cache_path, self.check_file_exists(cache_path)

    @staticmethod
    def save_cache(cache_path, output):
        if not os.path.isdir(CACHE_DIR):
            os.mkdir(CACHE_DIR, 0755)
        with open(cache_path, "wb") as f_cache:
            f_cache.write(output.encode(CHARSET))
        return True

    # pages
    @staticmethod
    def get_files(base_dir, ext):
        all_files = []
        for root, directory, files in os.walk(base_dir):
            file_full_paths = [os.path.join(root, f) for f in filter(lambda x: x.endswith(ext), files)]
            all_files.extend(file_full_paths)
        return all_files

    def get_pages(self, sort_key="title", reverse=False):
        files = self.get_files(CONTENT_DIR, CONTENT_FILE_EXT)
        file_data_list = []
        for f in files:
            relative_path = f.split(CONTENT_DIR, 1)[1]
            if relative_path.startswith("~") \
                    or relative_path.startswith("#") \
                    or relative_path in self.content_ignore_files:
                continue
            with open(f, "r") as fh:
                file_content = fh.read().decode(CHARSET)
            meta_string, content_string = self.content_splitter(file_content)
            meta = self.parse_file_meta(meta_string)
            data = dict()
            # generate request url
            if relative_path.endswith(CONTENT_FILE_EXT):
                relative_path = relative_path[:-len(CONTENT_FILE_EXT)]

            if relative_path.endswith("index"):
                relative_path = relative_path[:-5]

            url = "/{}".format(relative_path)

            data["path"] = f
            data["title"] = meta.get("title", "")
            data["url"] = url
            data["author"] = meta.get("author", "")
            data["date"] = meta.get("date", "")
            data["description"] = meta.get("description", "")
            g.view_ctx["tmp"]["page_data"] = data
            g.view_ctx["tmp"]["page_meta"] = meta
            self.run_hook("get_page_data")
            file_data_list.append(g.view_ctx["tmp"]["page_data"])
        self.pop_item_in_dict(g.view_ctx["tmp"], "page_data", "page_meta")
        if sort_key not in ("title", "date"):
            sort_key = "title"
        return sorted(file_data_list, key=lambda x: u"{}_{}".format(x[sort_key], x["title"]), reverse=reverse)

    #theme
    @property
    def theme_name(self):
        return current_app.config.get("THEME_NAME")

    def theme_path_for(self, tmpl_name):
        return os.path.join(self.theme_name, "{}{}".format(tmpl_name, TEMPLATE_FILE_EXT))

    # context
    def init_context(self):
        config = current_app.config
        g.view_ctx["config"] = config
        g.view_ctx["base_url"] = config.get("BASE_URL")
        g.view_ctx["theme_path_for"] = self.theme_path_for
        g.view_ctx["site_title"] = config.get("SITE_TITLE")
        g.view_ctx["site_author"] = config.get("SITE_AUTHOR")
        g.view_ctx["site_description"] = config.get("SITE_DESCRIPTION")
        return

    #hook
    def run_hook(self, hook_name, *cleanup_keys):
        for plugin_module in g.plugins:
            func = plugin_module.__dict__.get(hook_name)
            if callable(func):
                func()
        self.cleanup_context(*cleanup_keys)
        return

    # cleanup
    @staticmethod
    def pop_item_in_dict(d, *keys):
        for key in keys:
            if key in d:
                d.pop(key)
        return

    def cleanup_context(self, *keys):
        self.pop_item_in_dict(g.view_ctx, *keys)
        return


class ContentView(BaseView):
    def get(self, _, is_auto_index=False):
        # init
        self.init_context()
        status_code = 200
        is_not_found = False
        content_file_full_path = None
        cache_full_path = None
        enable_cache = current_app.config.get("ENABLE_CACHE")
        run_hook = self.run_hook
        etag = None

        # load
        load_plugins()
        run_hook("plugins_loaded")

        load_config(current_app)
        run_hook("config_loaded")

        request_url = request.path
        g.view_ctx["request"] = request
        run_hook("request_url", "request")

        if not is_auto_index:
            content_file_full_path = self.get_file_path(request_url)
            # hook before load content
            g.view_ctx["file_path"] = content_file_full_path
            run_hook("before_load_content")
            # if not found
            if content_file_full_path is None:
                is_not_found = True
                status_code = 404
                content_file_full_path = g.view_ctx["not_found_file_path"] = self.content_not_found_full_path
                if not self.check_file_exists(content_file_full_path):
                    # without not found file
                    abort(404)

            etag = self.generate_etag(content_file_full_path)

            # read cache content
            if enable_cache:
                cache_full_path, cache_exists = self.check_cache(content_file_full_path)
                if cache_exists:
                    return send_file(cache_full_path, mimetype="text/html; charset=utf-8")

            # read file content
            if is_not_found:
                run_hook("before_404_load_content")
            with open(content_file_full_path, "r") as f:
                g.view_ctx["file_content"] = f.read().decode(CHARSET)
            if is_not_found:
                run_hook("after_404_load_content", "not_found_file_path")
            run_hook("after_load_content", "file_path")

            # parse file content
            meta_string, content_string = self.content_splitter(g.view_ctx["file_content"])

            g.view_ctx["meta"] = self.parse_file_meta(meta_string)
            run_hook("file_meta")

            g.view_ctx["content_string"] = content_string
            run_hook("before_parse_content", "content_string")
            g.view_ctx["content"] = markdown.markdown(content_string, extensions=["fenced_code", "codehilite"])
            run_hook("after_parse_content")

        # content index
        g.view_ctx["pages"] = self.get_pages("date", True)
        g.view_ctx["current_page"] = defaultdict(str)
        g.view_ctx["prev_page"] = defaultdict(str)
        g.view_ctx["next_page"] = defaultdict(str)
        g.view_ctx["is_front_page"] = False
        g.view_ctx["is_tail_page"] = False
        for page_index, page_data in enumerate(g.view_ctx["pages"]):
            if is_auto_index:
                break
            if page_data["path"] == content_file_full_path:
                g.view_ctx["current_page"] = page_data
                if page_index == 0:
                    g.view_ctx["is_front_page"] = True
                else:
                    g.view_ctx["prev_page"] = g.view_ctx["pages"][page_index-1]
                if page_index == len(g.view_ctx["pages"]) - 1:
                    g.view_ctx["is_tail_page"] = True
                else:
                    g.view_ctx["next_page"] = g.view_ctx["pages"][page_index+1]
            page_data.pop("path")
        run_hook("get_pages")

        g.view_ctx["template_file_path"] = self.theme_path_for(DEFAULT_INDEX_TMPL_NAME) if is_auto_index \
            else self.theme_path_for(g.view_ctx["meta"].get("template", DEFAULT_POST_TMPL_NAME))

        run_hook("before_render")
        g.view_ctx["output"] = render_template(g.view_ctx["template_file_path"], **g.view_ctx)
        run_hook("after_render", "template_file_path")

        # save cache
        if enable_cache and cache_full_path:
            self.save_cache(cache_full_path, g.view_ctx["output"])

        return make_content_response(g.view_ctx["output"], status_code, etag)


app = Flask(__name__, static_url_path=STATIC_BASE_URL)
load_config(app)
app.static_folder = STATIC_DIR
app.template_folder = THEME_DIR
auto_index = app.config.get("AUTO_INDEX")
app.add_url_rule("/favicon.ico", redirect_to="{}/favicon.ico".format(STATIC_BASE_URL), endpoint="favicon.ico")
app.add_url_rule("/", defaults={"_": "", "is_auto_index": auto_index}, view_func=ContentView.as_view("index"))
app.add_url_rule("/<path:_>", view_func=ContentView.as_view("content"))


@app.before_request
def injection():
    g.plugins = []
    g.view_ctx = dict()
    g.view_ctx["tmp"] = dict()
    return


@app.errorhandler(Exception)
def errorhandler(err):
    err_msg = "{}".format(repr(err))
    current_app.logger.error(err_msg)
    return make_response(err_msg, 579)


if __name__ == "__main__":
    host = app.config.get("HOST")
    port = app.config.get("PORT")
    debug = app.config.get("DEBUG")
    app.run(host=host, port=port, debug=debug)