def set_if_not_none(mapping: dict, key: str, value: str, new_key: str, new_relation: str):
    if "date"  in key:
        new_relation = ""
    if key:
        mapping[f"{new_relation}{new_key}"] = value


def filter_trips(qs: "Queryset", filter_query: dict = None, new_relation: str = "") -> "Queryset":
    # new_relation is used for additional lookup. in this funtion Trips and RideExpense modal 
    # can pass for filtering. for RideExpense trips__ is the additional lookup used for get data inside trips.

    if filter_query is None:
        return qs

    name_mapping = {
        "member_uuids": "assigned_to__uuid__in",
        "department_uuids": "assigned_to__department__uuid__in",
        "designation_uuids": "assigned_to__designation__uuid__in",
        "role_uuids": "assigned_to__role__uuid__in",
        "created_by_uuids": "created_by__uuid__in",
        "start_location_uuids": "start_location_ptr__uuid__in",
        "end_location_uuids": "end_location_ptr__uuid__in",
        "start_date": "created_at__date__gte",
        "end_date": "created_at__date__lte",
        "status": "status__in",
        "priority": "priority__in",
        "started_on": "trip_details__start_scan__created_at",
        "ended_on": "trip_details__end_scan__created_at",
        "organization_location_uuids": "assigned_to__organization_location__uuid__in",
        "trip_uuids": "uuid__in",
    }
    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        if value:
            set_if_not_none(filter_query_dict, key, value, new_key, new_relation)
    return qs.filter(**filter_query_dict)


def convert_query_params_to_dict(query_params: dict) -> dict:

    new_dict = {}
    for key in query_params.keys():
        if "uuid" in key or key in ["status", "priority", "organization_location"]:
            # only picking values from query_params.getlist(key) if its not empty
            new_dict[key] = [values for values in query_params.getlist(key) if values] 
        else:
            new_dict[key] = query_params.get(key)
    return new_dict



def filter_expenses(qs: "Queryset", filter_query: dict = None, new_relation: str = "") -> "Queryset":
    # new_relation is used for additional lookup. in this funtion Trips and RideExpense modal 
    # can pass for filtering. for RideExpense trips__ is the additional lookup used for get data inside trips.

    if filter_query is None:
        return qs

    name_mapping = {
        "status": "status__in",
        "start_date": "created_at__date__gte",
        "end_date": "created_at__date__lte",
    }
    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        if value:
            set_if_not_none(filter_query_dict, key, value, new_key, new_relation)
    return qs.filter(**filter_query_dict)
