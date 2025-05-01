from django.contrib.postgres.search import SearchVector, SearchQuery
from django.db.models import Q
from utils.utils import create_search_filter

MEMBER_SEARCH_FIELDS = [
    "user__first_name",
    "user__last_name",
    "user__email",
    "user__phone_number",
    "role__name",
]


def search_members(qs: "Queryset", search_query: str) -> "Queryset":
    if search_query is None:
        return qs

    filters = create_search_filter(MEMBER_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
