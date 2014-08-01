#coding=utf-8
from __future__ import absolute_import
from flask import g, request


DEFAULT_PAGINATION_LIMIT = 10


def request_url():
    if g.view_ctx.get("is_site_index") is True:
        try:
            current_page = max(int(request.args.get("page")), 1)
        except (ValueError, TypeError):
            current_page = 1
        g.view_ctx["pagination_current_page"] = current_page
    return


def get_pages():
    current_page = g.view_ctx.get("pagination_current_page")
    if current_page and isinstance(current_page, int):
        pagination_limit = g.config.get("PAGINATION_LIMIT", DEFAULT_PAGINATION_LIMIT)
        total = page_count(pagination_limit, len(g.view_ctx["pages"]))
        current_page = min(current_page, total)
        start = (current_page-1)*pagination_limit
        end = current_page*pagination_limit
        g.view_ctx["pages"] = g.view_ctx["pages"][start:end]
        g.view_ctx["pagination"] = dict()
        g.view_ctx["pagination"]["current_page"] = current_page
        g.view_ctx["pagination"]["has_prev_page"] = current_page > 1
        g.view_ctx["pagination"]["has_next_page"] = current_page < total
    return


def page_count(pagination_limit, total):
    return max((total+pagination_limit-1)/pagination_limit, 1)