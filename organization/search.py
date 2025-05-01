from django.contrib.postgres.search import SearchVector, SearchQuery
from django.db.models import Q
from utils.utils import create_search_filter


SEARCH_FIELDS = ["name", "description"]
LOCATION_SEARCH_FIELDS = ["name", "description"]
COST_MATRIX_SEARCH_FIELDS = (
    "fuel__name",
    "fuel__description",
    "vehicle__name",
    "vehicle__description",
    "cost_per_unit",
)


def search_fuels(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_vehicles(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_locations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs


    # search_vector = SearchVector(*LOCATION_SEARCH_FIELDS)
    # query_for_search = " | ".join(search_query.split())
    # return  qs.annotate(search=search_vector).filter(
    #     Q(search=SearchQuery(query_for_search, search_type='raw')) | Q(search__icontains=search_query)
    # )

    # return qs.annotate(search=SearchVector(*LOCATION_SEARCH_FIELDS)).filter(
    #     search__icontains=search_query
    # )
    filters = create_search_filter(LOCATION_SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_departments(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_FIELDS, search_query)
    return qs.filter(filters)


def search_destinations(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(SEARCH_FIELDS, search_query)
    return qs.filter(filters)

def search_cost_matrices(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None:
        return qs

    filters = create_search_filter(COST_MATRIX_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
