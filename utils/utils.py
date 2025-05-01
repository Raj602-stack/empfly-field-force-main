from django.db.models import Q

def create_search_filter(fields: list, search_query):
    search_query = search_query.strip().lower()

    filters = None
    for field in fields:
        field_data = f"{field}__icontains"
        data = {field_data: search_query}

        if filters is None:
            filters = Q(**data)

        filters |= Q(**data)

    return filters
