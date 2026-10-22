"""Shared helpers for paginated, filterable list views."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_date

PAGE_SIZE = 100


def build_search_q(search_term, fields, *, date_fields=None, include_pk=True):
    """
    Build an OR Q() across text fields (icontains).

    When include_pk is True and the term is numeric, also match primary key.
    Date-looking terms also match exact values on date_fields.
    """
    term = (search_term or '').strip()
    if not term:
        return Q()

    query = Q()
    for field in fields:
        query |= Q(**{f'{field}__icontains': term})

    if include_pk and term.isdigit():
        query |= Q(pk=int(term))

    parsed = parse_date(term)
    if parsed is not None:
        for field in (date_fields or ()):
            query |= Q(**{field: parsed})

    return query


def paginate_queryset(queryset, page_number, per_page=PAGE_SIZE):
    """
    Paginate a queryset and build range labels like 1-100, 101-200.
    """
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page_number)

    page_range_choices = []
    for num in paginator.page_range:
        start = (num - 1) * per_page + 1
        end = min(num * per_page, paginator.count)
        page_range_choices.append({'page': num, 'label': f'{start}-{end}'})

    return {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range_choices': page_range_choices,
        'is_paginated': page_obj.has_other_pages(),
    }


def filter_query_string(request, *exclude_keys):
    """Preserve current GET filters for pagination links (drops page by default)."""
    params = {}
    excluded = {'page', *exclude_keys}
    for key, value in request.GET.items():
        if key in excluded or value in (None, ''):
            continue
        params[key] = value
    return urlencode(params)
