from django.contrib.postgres.search import SearchVector
from utils.utils import create_search_filter


RIDE_EXPENSE_SEARCH_FIELDS = [
    "trip__name",
    "trip__description",
]


def search_expenses(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(RIDE_EXPENSE_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

ALL_RIDE_EXPENSE_SEARCH_FIELDS = [
    "trip__name",
]

def search_all_expenses(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(ALL_RIDE_EXPENSE_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
