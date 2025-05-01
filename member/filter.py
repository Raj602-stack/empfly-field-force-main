def set_if_not_none(mapping: dict, key: str, value: str, new_key: str):
    if key:
        mapping[new_key] = value


def filter_members(qs: "Queryset", filter_query: dict = None) -> "Queryset":

    if filter_query is None:
        return qs

    # Convert query parameters to ORM filters
    name_mapping = {
        "member_uuids": "uuid__in",
        "department_uuids": "department__uuid__in",
        "designation_uuids": "designation__uuid__in",
        "role_uuids": "role__uuid__in",
        "organization_location_uuids": "organization_location__uuid__in",
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
        if "uuid" in key:
            new_dict[key] = query_params.getlist(key)
        else:
            new_dict[key] = query_params.get(key)
    return new_dict
