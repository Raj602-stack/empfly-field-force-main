from celery import shared_task

from export.models import ExportRequest
from export.utils import (
    export_field_report_submission_csv,
    export_location_csv,
    export_member_expense_to_csv,
    export_member_trips_to_csv,
    export_trips_to_csv,
    update_export_request,
    export_members_to_csv,
    export_department_to_csv,
    export_expense_to_csv,
    export__reimbursement_requests_to_csv,
    export_admin_report_submission_csv,
    export_create_trip_submission_csv
)

import json
import logging


logger = logging.getLogger(__name__)


@shared_task(name="export_requests_task")
def export_requests_task():
    export_requests = ExportRequest.objects.filter(status="pending")
    for export_request in export_requests:

        converted_data = json.loads(export_request.content)
        object_type = converted_data.get("object_type")
        object_ids = converted_data.get("object_ids")

        if object_type == "trip":
            # trip register list
            filename = export_trips_to_csv(export_request, object_ids)
        if object_type == "member":
            # employees list
            filename = export_members_to_csv(export_request, object_ids)
        if object_type == "department":
            # department list
            filename = export_department_to_csv(export_request, object_ids)
        if object_type == "expense":
            # all ride expense list
            filename = export_expense_to_csv(export_request, object_ids)      
        if object_type == "reimbursement_requests":
            # reimbursement requests list
            filename = export__reimbursement_requests_to_csv(export_request, object_ids)
        if object_type == "members_ride_expense":
            # CSV of the RideExpenses modal
            filename = export_member_expense_to_csv(export_request, object_ids, export_request.member.organization)
        if object_type == "members_trips":
            # CSV of the trips modal
            filename = export_member_trips_to_csv(export_request, object_ids, export_request.member.organization)
        # CSV of the Location modal
        if object_type == "locations":
            filename =  export_location_csv(export_request, object_ids)

        if object_type == "field_report_submission":
            filename =  export_field_report_submission_csv(export_request, object_ids)

        if object_type == "admin_report_submission":
            filename =  export_admin_report_submission_csv(export_request, object_ids)

        if object_type == "create_trip_submission":
            filename =  export_create_trip_submission_csv(export_request, object_ids)

        update_export_request(export_request, filename)
