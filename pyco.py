#coding=utf-8
from __future__ import absolute_import

CONTENT_DIR = "content/"
PLUGIN_DIR = "plugins/"
THEME_DIR = "theme/"
STATIC_DIR = "static/"
STATIC_BASE_URL = "/static"
CONTENT_FILE_EXT = ".md"

import sys
sys.path.insert(0, PLUGIN_DIR)

from flask import Flask, current_app, request, abort, render_template, g, make_response
from flask.views import MethodView
import os
import re
from utils import load_config, run_hook, load_plugins
from collections import defaultdict
import markdown


class BaseView(MethodView):
    # common
    def get_file_path(self, url):
        full_path = os.path.join(self.content_base_dir, url[1:])

        dir_name = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)

        base_path = os.path.join(dir_name, file_name) if file_name else dir_name

        file_name = "{}{}".format(base_path, self.content_file_ext)
        if self.check_is_file(file_name):
            return file_name

        file_name = os.path.join(base_path, "index{}".format(self.content_file_ext))
        if self.check_is_file(file_name):
            return file_name
        return None

    @staticmethod
    def check_is_file(filename):
        return os.path.isfile(filename)

    # site property
    @property
    def site_title(self):
        return current_app.config.get("SITE_TITLE")

    @property
    def base_url(self):
        return current_app.config.get("BASE_URL")

    @property
    def site_author(self):
        return current_app.config.get("SITE_AUTHOR")

    # content
    @property
    def content_base_dir(self):
        return CONTENT_DIR

    @property
    def content_file_ext(self):
        return CONTENT_FILE_EXT

    @property
    def not_found_filename(self):
        return "{}{}".format(current_app.config.get("NOT_FOUND_FILE"), self.content_file_ext)

    @property
    def not_found_file_path(self):
        return os.path.join(self.content_base_dir, self.not_found_filename)

    @property
    def site_index_filename(self):
        return "{}{}".format(current_app.config.get("SITE_INDEX_FILE"), self.content_file_ext)

    @property
    def site_index_file_path(self):
        return os.path.join(self.content_base_dir, self.site_index_filename)

    @property
    def post_date_format(self):
        return current_app.config.get("POST_DATE_FORMAT")

    @property
    def ignore_files(self):
        return current_app.config.get("IGNORE_FILES")

    @staticmethod
    def content_splitter(file_content):
        pattern = r"(\n)*/\*(\n)*(?P<meta>(.*\n)*)\*/(?P<content>(.*(\n)?)*)"
        re_pattern = re.compile(pattern)
        m = re_pattern.match(file_content)
        if m is None:
            return "", ""
        return m.group("meta"), m.group("content")

    @staticmethod
    def parse_file_meta(meta_string):
        headers = dict()
        run_hook("before_read_file_meta")
        for line in meta_string.split("\n"):
            kv_pair = line.split(":", 1)
            if len(kv_pair) == 2:
                headers[kv_pair[0].lower()] = kv_pair[1].strip()
        return headers

    # theme
    @property
    def theme_base_dir(self):
        return THEME_DIR

    @property
    def theme_name(self):
        return current_app.config.get("THEME_NAME")

    @property
    def theme_dir(self):
        return os.path.join(self.theme_base_dir, self.theme_name)

    def theme_file_path(self, tmpl_name):
        return os.path.join(self.theme_name, "{}.html".format(tmpl_name))

    @staticmethod
    def parse_content(file_content):
        return

    # pages
    @staticmethod
    def get_files(base_dir, ext):
        all_files = []
        for root, directory, files in os.walk(base_dir):
            for f in filter(lambda x: x.endswith(ext), files):
                p = os.path.join(root, f)
                all_files.append(p)
        return all_files

    def get_pages(self, sort_key="title", reverse=False):
        files = self.get_files(self.content_base_dir, self.content_file_ext)
        file_data_list = []
        for f in files:
            relative_path = f.split(self.content_base_dir, 1)[1]
            if relative_path.startswith("~") \
                    or relative_path.startswith("#") \
                    or relative_path == self.not_found_filename \
                    or relative_path == self.site_index_filename \
                    or relative_path in self.ignore_files:
                continue
            with open(f, "r") as fh:
                file_content = fh.read().decode("utf8")
            meta_string, content_string = self.content_splitter(file_content)
            meta = self.parse_file_meta(meta_string)
            data = dict()
            url = "/{}".format(relative_path)
            if url.endswith(self.content_file_ext):
                url = url[:-len(self.content_file_ext)]

            if url.endswith("/index"):
                url = url[:-6]
            if url == "":
                url = "/"
            data["path"] = f
            data["title"] = meta.get("title", "")
            data["url"] = url
            data["author"] = meta.get("author", "")
            data["date"] = meta.get("date", "")
            g.view_ctx["tmp"]["page_data"] = data
            g.view_ctx["tmp"]["page_meta"] = meta
            run_hook("get_page_data")
            file_data_list.append(g.view_ctx["tmp"]["page_data"])
        if sort_key not in ("title", "date"):
            sort_key = "title"
        return sorted(file_data_list, key=lambda x: x[sort_key], reverse=reverse)

    # handler
    def get_context(self):
        g.view_ctx["config"] = current_app.config
        g.view_ctx["base_url"] = self.base_url
        g.view_ctx["theme_file_path"] = self.theme_file_path
        g.view_ctx["site_title"] = self.site_title
        g.view_ctx["site_author"] = self.site_author
        return


class ContentView(BaseView):
    def get(self, _, is_index=False):
        status_code = 200

        self.get_context()

        load_plugins()
        run_hook("plugins_loaded")

        load_config(current_app)
        run_hook("config_loaded")

        request_url = request.path
        g.view_ctx["request"] = request
        run_hook("request_url")

        if not is_index:
            g.view_ctx["file_path"] = self.get_file_path(request_url)
            run_hook("before_load_content")

            if g.view_ctx["file_path"] is None:
                if not self.check_is_file(self.not_found_file_path):
                    abort(404)
                g.view_ctx["not_found_file_path"] = self.not_found_file_path

                run_hook("before_404_load_content")
                with open(g.view_ctx["not_found_file_path"], "r") as f:
                    g.view_ctx["file_content"] = f.read().decode("utf8")

                run_hook("after_404_load_content")
                status_code = 404
            else:
                with open(g.view_ctx["file_path"], "r") as f:
                    g.view_ctx["file_content"] = f.read().decode("utf8")

            run_hook("after_load_content")

            meta_string, content_string = self.content_splitter(g.view_ctx["file_content"])

            g.view_ctx["meta"] = self.parse_file_meta(meta_string)
            run_hook("file_meta")

            run_hook("before_parse_content")
            g.view_ctx["content"] = markdown.markdown(content_string, extensions=["fenced_code", "codehilite"])
            run_hook("after_parse_content")

        g.view_ctx["pages"] = self.get_pages("date", True)
        g.view_ctx["current_page"] = defaultdict(str)
        g.view_ctx["prev_page"] = defaultdict(str)
        g.view_ctx["next_page"] = defaultdict(str)
        g.view_ctx["is_front_page"] = False
        g.view_ctx["is_tail_page"] = False
        for page_index, page_data in enumerate(g.view_ctx["pages"]):
            if not is_index and page_data["path"] == g.view_ctx["file_path"]:
                g.view_ctx["current_page"] = page_data
                if page_index == 0:
                    g.view_ctx["is_front_page"] = True
                else:
                    g.view_ctx["prev_page"] = g.view_ctx["pages"][page_index-1]
                if page_index == len(g.view_ctx["pages"]) - 1:
                    g.view_ctx["is_tail_page"] = True
                else:
                    g.view_ctx["next_page"] = g.view_ctx["pages"][page_index+1]
        run_hook("get_pages")

        g.view_ctx["template_file_path"] = self.theme_file_path("index") if is_index \
            else self.theme_file_path(g.view_ctx["meta"].get("template", "post"))

        run_hook("before_render")
        g.view_ctx["output"] = render_template(g.view_ctx["template_file_path"], **g.view_ctx)
        run_hook("after_render")
        return make_response(g.view_ctx["output"], status_code)


app = Flask(__name__, static_url_path=STATIC_BASE_URL)
load_config(app)
app.static_folder = STATIC_DIR
app.template_folder = THEME_DIR
auto_index = app.config.get("AUTO_INDEX")
app.add_url_rule("/", defaults={"_": "", "is_index": auto_index}, view_func=ContentView.as_view("index"))
app.add_url_rule("/<path:_>", view_func=ContentView.as_view("content"))


@app.before_request
def injection():
    g.plugins = []
    g.view_ctx = dict()
    g.view_ctx["tmp"] = dict()
    return


if __name__ == "__main__":
    host = app.config.get("HOST")
    port = app.config.get("PORT")
    debug = app.config.get("DEBUG")
    app.run(host=host, port=port, debug=debug)