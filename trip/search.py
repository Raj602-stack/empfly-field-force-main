from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Q
from utils.utils import create_search_filter

TRIP_SEARCH_FIELDS = [
    "name",
    "description",
    "start_location__name",
    "start_location__latitude",
    "start_location__longitude",
    "end_location__name",
    "end_location__latitude",
    "end_location__longitude",
    "assigned_to__user__first_name",
    "assigned_to__user__last_name",
    "assigned_to__user__email",
    "assigned_to__user__phone_number",
    "start_location_ptr__name",
    "start_location_ptr__latitude",
    "start_location_ptr__longitude",
    "end_location_ptr__name",
    "end_location_ptr__latitude",
    "end_location_ptr__longitude",
]

RIDE_EXP_SEARCH_FIELDS = [
    "trip__name",
    "description",
    "trip__start_location__name",
    "trip__start_location__latitude",
    "trip__start_location__longitude",
    "trip__end_location__name",
    "trip__end_location__latitude",
    "trip__end_location__longitude",
    "trip__assigned_to__user__first_name",
    "trip__assigned_to__user__last_name",
    "trip__assigned_to__user__email",
    "trip__assigned_to__user__username",
    "trip__assigned_to__user__phone_number",
    "trip__start_location_ptr__name",
    "trip__start_location_ptr__latitude",
    "trip__start_location_ptr__longitude",
    "trip__end_location_ptr__name",
    "trip__end_location_ptr__latitude",
    "trip__end_location_ptr__longitude",
]


def search_trips(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None or search_query == "":
            return qs
    
    filters = create_search_filter(TRIP_SEARCH_FIELDS, search_query)
    return qs.filter(filters)



def search_ride_expeses(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None or search_query == "":
            return qs

    filters = create_search_filter(RIDE_EXP_SEARCH_FIELDS, search_query)
    return qs.filter(filters)



ALL_TRIP_SEARCH_FIELDS = [
    "name",
]

# TODO search only required som field . do check if the search trip fun is need
def search_all_trips(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None or search_query == "":
            return qs
    
    filters = create_search_filter(ALL_TRIP_SEARCH_FIELDS, search_query)
    return qs.filter(filters)



ALL_RIDE_EXP_SEARCH_FIELDS = [
    "trip__name"
]


def search_all_ride_expeses(qs: "Queryset", search_query: str) -> "Queryset":

    if search_query is None or search_query == "":
            return qs

    filters = create_search_filter(ALL_RIDE_EXP_SEARCH_FIELDS, search_query)
    return qs.filter(filters)
