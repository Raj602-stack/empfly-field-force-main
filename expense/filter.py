
def set_if_not_none(mapping: dict, key: str, value: str, new_key: str):
    if key:
        mapping[new_key] = value


def filter_expenses(qs: "Queryset", filter_query: dict = None) -> "Queryset":

    if filter_query is None:
        return qs

    name_mapping = {
        "member_uuids": "trip__assigned_to__uuid__in",
        "department_uuids": "trip__assigned_to__department__uuid__in",
        "designation_uuids": "trip__assigned_to__designation__uuid__in",
        "role_uuids": "trip__assigned_to__role__uuid__in",
        "created_by_uuids": "trip__created_by__uuid__in",
        "start_location_uuids": "trip__start_location_ptr__uuid__in",
        "end_location_uuids": "trip__end_location_ptr__uuid__in",
        "start_date": "trip__created_at__date__gte",
        "end_date": "trip__created_at__date__lte",
        "status": "status__in",
        "priority": "trip__priority__in",
        "start_amount": "amount__gte",
        "end_amount": "amount__lte",
        "approved_by_uuids": "approved_by__uuid__in",
        "reimbursed_by_uuids": "reimbursed_by__uuid__in",
        "payment_mode_uuids": "payment_mode__uuid__in",
        "fuel_uuids": "fuel__uuid__in",
        "vehicle_uuids": "vehicle__uuid__in",
        "organization_location_uuids": "trip__assigned_to__organization_location__uuid__in",
    }

    filter_query_dict = {}
    for key, value in filter_query.items():
        new_key = name_mapping.get(key)
        if new_key is None:
            continue
        set_if_not_none(filter_query_dict, key, value, new_key)

    return qs.filter(**filter_query_dict)


def convert_query_params_to_dict(query_params: dict) -> dict:

    new_dict = {}
    for key in query_params.keys():
        if "uuid" in key or key in ["status", "priority"]:
            new_dict[key] = query_params.getlist(key)
        else:
            new_dict[key] = query_params.get(key)
    return new_dict
