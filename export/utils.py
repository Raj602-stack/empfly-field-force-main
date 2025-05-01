import os
import json
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from expense.models import RideExpense
from expense.serializers import RideExpenseSerializer
from field_force.settings import UI_DOMAIN_URL
from form_builder.constants import FIELD_REPORT_FORM_CONFIG_FIELDS, ADMIN_REPORT_CONFIG_FIELDS, CREATE_TRIP_FORM_CONFIG_FIELDS
from form_builder.models import FieldReportFormSubmissions, AdminReportFormSubmissions, CreateTripFormSubmissions
from form_builder.serializers import FieldReportFileSerializer
from utils.read_data import (
    convert_dt_to_another_tz,
    convert_submission_data_to_str,
    empty_or_data,
    extract_data_from_object,
    extract_data_from_dict,
    remove_dt_millie_sec,
    string_to_dt,
)
from .helper import check_key_exist, get_or_return_NA
from export.models import ExportRequest
from member.models import Member
from member.serializers import MemberSerializer
from organization.models import Department, Location
from organization.serializers import DepartmentSerializer, LocationSerializer
from member.helper import (
    get_member_status_details,
    get_ride_exp_report_data,
    get_trip_report_data,
)
from trip.models import Trip
from trip.serializers import TripSerializer

from uuid import uuid4
import time
import csv
import logging
from trip.models import Trip
from django.db.models import Q
from utils.read_data import extract_data_from_object, empty_or_data

logger = logging.getLogger(__name__)


def get_export_request(member: Member, uuid: uuid4) -> ExportRequest:
    """Get export data ins using member and uuid of export data"""

    try:
        return ExportRequest.objects.get(uuid=uuid, member=member)
    except (ValidationError, ExportRequest.DoesNotExist) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_export_request"
        )
    return None


def create_export_request(
    member: Member, object_type: str, object_ids: list
) -> ExportRequest:
    """Create export request for csv."""

    # object_type is used for identify which models data is exporting
    # object_ids are PK of model which user want to export
    content = json.dumps({"object_type": object_type, "object_ids": object_ids})

    try:
        is_duplicate = ExportRequest.objects.filter(
            Q(member=member) & Q(content=content) & Q(status="pending")
        ).exists()

        if not is_duplicate:
            exportRequest = ExportRequest.objects.create(member=member, content=content)

            # assign task
            # to avoid circular import error
            # added import inside function
            from export.tasks import export_requests_task

            # add task to queue
            export_requests_task.apply_async(
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.2,
                    "interval_max": 0.2,
                },
            )

            return exportRequest
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in create_export_request"
        )

    return None


# def export_request_get_or_create(member: Member, object_type: str, object_ids: list) -> ExportRequest:

#     content = json.dumps({"object_type": object_type, "object_ids": object_ids})

#     try:
#         export_req = ExportRequest.objects.filter(Q(member=member) & Q(content=content) & Q(status="pending"))
#         if export_req.exists():
#             return export_req[0]

#         return ExportRequest.objects.create(member=member, content=content)
#     except Exception as e:
#         logger.error(e)
#         logger.exception(f"Add exception for {e.__class__.__name__} in create_export_request")

#     return None


def update_export_request(
    export_request: ExportRequest, filename: str
) -> ExportRequest:
    content = json.loads(export_request.content)
    objectType = (
        content.get("object_type", "temp")
        if content.get("object_type", "temp")
        else "temp"
    )

    export_request.status = "completed"
    export_request.link = f"media/{objectType}/csv/{filename}.csv"
    export_request.save()


def get_current_time() -> float:
    return time.time()


def generate_file_suffix(export_request: ExportRequest) -> str:
    """User for name the file or name the export csv file."""
    request_id = export_request.request_id
    current_time = get_current_time()
    return f"{request_id}__{current_time}"


def export_trips_to_csv(export_request: ExportRequest, trip_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"trip__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/trip/csv/"):
        os.makedirs("media/trip/csv/")
    with open(f"media/trip/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip_name",
                "trip_assigned_to",
                "raised_by",
                "trip created date",
                "trip created time",
                "start_location_name",
                "start_location_coordinates",
                "end_location_name",
                "end_location_coordinates",
                "priority",
                "status",
                "estimated_distance",
                "actual_distance",
                "start_scan_note",
                "end_scan_note",
                "trip_remarks",
                "completed by",
                "employee id",
                "trip description",
                "start time",
                "end time",
                "actual start location",
                "actual start location coordinates",
                "actual end location",
                "actual end location coordinates",
                "within geo-fencing",
                "estimated duration",
                "actual duration",
            ]
        )

        trips = Trip.objects.filter(id__in=trip_ids, assigned_to__isnull=False)

        for trip_data in trips:

            start_location = trip_data.start_location
            end_location = trip_data.end_location

            created_by = ""
            if (
                trip_data.created_by
                and trip_data.created_by.user
                and trip_data.created_by.user.username
            ):
                created_by = trip_data.created_by.user.username

            assigned_user_email = ""
            if (
                trip_data.assigned_to
                and trip_data.assigned_to.user
                and trip_data.assigned_to.user.username
            ):
                assigned_user_email = trip_data.assigned_to.user.username

            start_lang = start_location.get("latitude", "")
            start_long = start_location.get("longitude", "")

            start_lang_and_long = f"{start_lang}{start_long}"

            # logger.error(
            #     f"={start_lang_and_long}= start location langtitude and logtitude. length of start_lang_and_long = {len(start_lang_and_long)}, type of start_lang_and_long = {type(start_lang_and_long)}"
            # )

            if start_lang_and_long and start_lang_and_long != "":
                start_lang_and_long = f"{start_lang},{start_long}"
            else:
                start_lang_and_long = ""

            end_lang = end_location.get("latitude", "")
            end_long = end_location.get("longitude", "")

            end_lang_and_long = f"{end_lang}{end_long}"

            # logger.error(
            #     f"={end_lang_and_long}= end location longitude and logtitude. length of end_lang_and_long = {len(end_lang_and_long)}, type of end_lang_and_long = {type(end_lang_and_long)}"
            # )

            if end_lang_and_long and end_lang_and_long != "":
                end_lang_and_long = f"{end_lang},{end_long}"
            else:
                end_lang_and_long = ""

            trip_details = trip_data.trip_details

            start_scan_note = ""
            if trip_details.start_scan:
                start_scan_note = trip_details.start_scan.notes.get("user_notes", "")

            end_scan_note = ""
            if trip_details.end_scan:
                end_scan_note = trip_details.end_scan.notes.get("user_notes", "")

            completed_by = extract_data_from_object(
                trip_data, ["assigned_to", "user", "username"]
            )

            employee_id = empty_or_data(
                extract_data_from_object(trip_data, ["assigned_to", "employee_id"])
            )

            trip_description = empty_or_data(
                extract_data_from_object(trip_data, ["description"])
            )

            # trip start and end time
            start_scan_dt = extract_data_from_object(
                trip_details, ["start_scan", "time"]
            )
            end_scan_dt = extract_data_from_object(trip_details, ["end_scan", "time"])

            actual_start_loc_name = None
            actual_start_loc_coords = None
            actual_end_loc_name = None
            actual_end_loc_coords = None

            if trip_details:
                start_scan_data = trip_details.start_scan
                if start_scan_data:
                    actual_start_loc_name = empty_or_data(
                        extract_data_from_object(start_scan_data, ["name"])
                    )

                    actual_start_loc_lat = empty_or_data(
                        extract_data_from_object(start_scan_data, ["latitude"])
                    )
                    actual_start_loc_long = empty_or_data(
                        extract_data_from_object(start_scan_data, ["longitude"])
                    )
                    actual_start_loc_coords = (
                        f"{actual_start_loc_lat},{actual_start_loc_long}"
                    )

                end_scan_data = trip_details.end_scan
                if end_scan_data:
                    actual_end_loc_name = empty_or_data(
                        extract_data_from_object(end_scan_data, ["name"])
                    )

                    actual_end_loc_lat = empty_or_data(
                        extract_data_from_object(end_scan_data, ["latitude"])
                    )
                    actual_end_loc_long = empty_or_data(
                        extract_data_from_object(end_scan_data, ["longitude"])
                    )
                    actual_end_loc_coords = (
                        f"{actual_end_loc_lat},{actual_end_loc_long}"
                    )

            within_geo_fencing = None
            if trip_details.start_scan and trip_details.end_scan:
                is_outside_geo_fencing = trip_data.is_outside_geo_fencing

                within_geo_fencing = {True: "No", False: "Yes"}.get(
                    is_outside_geo_fencing
                )

            estimated_duration = extract_data_from_object(
                trip_details, ["estimated_duration"]
            )
            actual_duration = extract_data_from_object(trip_details, ["duration"])

            created_at_dt = convert_dt_to_another_tz(trip_data.created_at)

            data = [
                trip_data.name,
                assigned_user_email,  # email
                created_by,  # email
                created_at_dt.date(),
                remove_dt_millie_sec(created_at_dt.time()),
                start_location.get("name", ""),
                start_lang_and_long,
                end_location.get("name", ""),
                end_lang_and_long,
                trip_data.priority,
                trip_data.status,
                get_or_return_NA(trip_details.estimated_distance),
                get_or_return_NA(trip_details.distance),
                start_scan_note,
                end_scan_note,
                get_or_return_NA(trip_details.comments.get("remarks")),
                empty_or_data(completed_by),
                empty_or_data(employee_id),
                empty_or_data(trip_description),
                empty_or_data(
                    remove_dt_millie_sec(convert_dt_to_another_tz(start_scan_dt))
                ),
                empty_or_data(
                    remove_dt_millie_sec(convert_dt_to_another_tz(end_scan_dt))
                ),
                empty_or_data(actual_start_loc_name),
                empty_or_data(actual_start_loc_coords),
                empty_or_data(actual_end_loc_name),
                empty_or_data(actual_end_loc_coords),
                empty_or_data(within_geo_fencing),
                empty_or_data(estimated_duration),
                empty_or_data(actual_duration),
            ]

            writer.writerow(data)

        # serializer = TripSerializer(trips, many=True)

        # for trip_data in serializer.data:

        #     assigned_to = trip_data.get("assigned_to", {}).get("user", {})
        #     created_by = trip_data.get("created_by", {}).get("user", {}).get("email")
        #     start_location = trip_data.get("start_location", {})
        #     end_location = trip_data.get("end_location", {})

        #     data = [
        #         trip_data.get("name"),
        #         assigned_to.get("email"),
        #         created_by,
        #         trip_data.get("created_at", "NA"),
        #         start_location.get("name"),
        #         "{},{}".format(start_location.get("latitude", ""), start_location.get("longitude", "")),
        #         end_location.get("name"),
        #         "{},{}".format(end_location.get("latitude", ""), end_location.get("longitude", "")),
        #         trip_data.get("priority", "NA"),
        #         trip_data.get("status", "NA"),
        #     ]
        #     writer.writerow(data)

    return filename


def export_members_to_csv(export_request: ExportRequest, member_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"member__{file_suffix}"
    # check if folder exists
    # if not creat directory

    if not os.path.exists("media/member/csv/"):
        os.makedirs("media/member/csv/")
    with open(f"media/member/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "email",
                "phone",
                "first_name",
                "last_name",
                "designation",
                "department",
                "organization_location",
                "employee_id",
                "manager",
                "role",
                "status",
            ]
        )
        objects = Member.objects.filter(id__in=member_ids)

        serializer = MemberSerializer(objects, many=True)

        bool_status_to_str = {True: "active", False: "inactive"}

        for data in serializer.data:

            user = data.get("user", {})

            csv_data = [
                data.get("id", "NA"),
                user.get("email", "NA"),
                user.get("phone_number", "NA"),
                user.get("first_name", "NA"),
                user.get("last_name", "NA"),
                check_key_exist(["name"], data.get("designation", {})),
                check_key_exist(["name"], data.get("department", {})),
                check_key_exist(["organization_location", "name"], data),
                get_or_return_NA(data.get("employee_id")),
                check_key_exist(["manager", "user", "email"], data),
                check_key_exist(["name"], data.get("role", {})),
                bool_status_to_str.get(user.get("is_active", True), ""),
            ]

            writer.writerow(csv_data)

    return filename


def export_department_to_csv(export_request: ExportRequest, dept_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"department__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/department/csv/"):
        os.makedirs("media/department/csv/")
    with open(f"media/department/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "name",
                "description",
                "department heads",
            ]
        )

        departments = Department.objects.filter(id__in=dept_ids)

        for department in departments:

            department_heads = department.department_head.all()
            department_head_emails: list = []
            for department_head in department_heads:
                department_head_emails.append(department_head.user.email)

            csv_data = [
                extract_data_from_object(department, ["uuid"]),
                extract_data_from_object(department, ["name"]),
                extract_data_from_object(department, ["description"]),
                ", ".join(department_head_emails)
            ]

            writer.writerow(csv_data)

    return filename


def export__reimbursement_requests_to_csv(
    export_request: ExportRequest, expense_ids: list
) -> csv:
    file_suffix = generate_file_suffix(export_request)
    filename = f"reimbursement_requests__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/reimbursement_requests/csv/"):
        os.makedirs("media/reimbursement_requests/csv/")
    with open(f"media/reimbursement_requests/csv/{filename}.csv", "w+") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip_name",
                "trip_assigned_to",
                "fuel",
                "vehicle",
                "amount",
                "reimbursed_amount",
                "status",
                "approved_by",
                "reimbursed_by",
                "trip_raised_on",
                "trip_start_time",
                "trip_end_time",
                "vehicle_mode",
                "estimated_distance",
                "actual_distance",
            ]
        )

        objects = RideExpense.objects.filter(id__in=expense_ids)
        serializer = RideExpenseSerializer(objects, many=True)

        for data in serializer.data:

            try:
                trip = Trip.objects.get(id=data.get("trip"))
            except Trip.DoesNotExist as e:
                trip = None

            if trip is not None:
                trip_data = TripSerializer(trip).data
            else:
                trip_data = {}

            trip_details = trip.trip_details

            fuel = data.get("fuel", {}) if data.get("fuel", {}) else {}
            vehicle = data.get("vehicle", {}) if data.get("vehicle", {}) else {}
            approved_by = (
                data.get("approved_by", {}) if data.get("approved_by", {}) else {}
            )
            reimbursed_by = (
                data.get("reimbursed_by", {}) if data.get("reimbursed_by", {}) else {}
            )

            csv_data = [
                trip_data.get("name", "NA"),
                # trip_data.get("assigned_to", {}).get("user", {}).get("email", "NA"),
                empty_or_data(
                    extract_data_from_dict(trip_data, ["assigned_to", "user", "email"])
                ),
                fuel.get("name", "NA"),
                vehicle.get("name", "NA"),
                data.get("amount", "NA"),
                data.get("reimbursement_amount", "NA"),
                data.get("status", "NA"),
                approved_by.get("user", {}).get("email", "NA"),
                reimbursed_by.get("user", {}).get("email", "NA"),
                remove_dt_millie_sec(
                    convert_dt_to_another_tz(trip_data.get("created_at"))
                ),
                get_or_return_NA(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            trip_details.start_scan.time
                            if trip_details.start_scan
                            else None
                        )
                    )
                ),
                get_or_return_NA(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            trip_details.end_scan.time
                            if trip_details.end_scan
                            else None
                        )
                    )
                ),
                get_or_return_NA(data.get("vehicle_mode", "NA")),
                get_or_return_NA(trip_details.estimated_distance),
                get_or_return_NA(trip_details.distance),
            ]

            writer.writerow(csv_data)

    return filename


def export_expense_to_csv(export_request: ExportRequest, expense_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"expenses__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/expense/csv/"):
        os.makedirs("media/expense/csv/")
    with open(f"media/expense/csv/{filename}.csv", "w+") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip_name",
                "trip_assigned_to",
                "fuel",
                "vehicle",
                "amount",
                "reimbursed_amount",
                "status",
                "approved_by",
                "reimbursed_by",
                "trip_raised_on",
                "trip_start_time",
                "trip_end_time",
                "vehicle_mode",
                "estimated_distance",
                "actual_distance",
            ]
        )

        objects = RideExpense.objects.filter(id__in=expense_ids)
        serializer = RideExpenseSerializer(objects, many=True)

        for data in serializer.data:

            try:
                trip = Trip.objects.get(id=data.get("trip"))
            except Trip.DoesNotExist as e:
                trip = None

            if trip is not None:
                trip_data = TripSerializer(trip).data
            else:
                trip_data = {}

            trip_details = trip.trip_details

            fuel = data.get("fuel", {}) if data.get("fuel", {}) else {}
            vehicle = data.get("vehicle", {}) if data.get("vehicle", {}) else {}
            approved_by = (
                data.get("approved_by", {}) if data.get("approved_by", {}) else {}
            )
            reimbursed_by = (
                data.get("reimbursed_by", {}) if data.get("reimbursed_by", {}) else {}
            )

            csv_data = [
                trip_data.get("name", "NA"),
                check_key_exist(["assigned_to", "user", "email"], trip_data),
                fuel.get("name", "NA"),
                vehicle.get("name", "NA"),
                data.get("amount", "NA"),
                data.get("reimbursement_amount", "NA"),
                data.get("status", "NA"),
                approved_by.get("user", {}).get("email", "NA"),
                reimbursed_by.get("user", {}).get("email", "NA"),
                remove_dt_millie_sec(
                    convert_dt_to_another_tz(trip_data.get("created_at"))
                ),
                get_or_return_NA(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            trip_details.start_scan.time
                            if trip_details.start_scan
                            else None
                        )
                    )
                ),
                get_or_return_NA(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            trip_details.end_scan.time
                            if trip_details.end_scan
                            else None
                        )
                    )
                ),
                get_or_return_NA(data.get("vehicle_mode", "NA")),
                get_or_return_NA(trip_details.estimated_distance),
                get_or_return_NA(trip_details.distance),
            ]

            writer.writerow(csv_data)

    return filename


def export_member_expense_to_csv(
    export_request: ExportRequest, expense_ids: list, org
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"members_ride_expenses__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/members_ride_expense/csv/"):
        os.makedirs("media/members_ride_expense/csv/")
    with open(f"media/members_ride_expense/csv/{filename}.csv", "w+") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "First name",
                "Last name",
                "Email",
                "Pending approval",
                "Pending reimbursement",
                "Approval rejected",
                "Reimbursement rejected",
                "Reimbursed",
                "Closed",
                "Total",
                "Estimated KMs (Total)",
                "Actual KMs (Total)",
                "Reimbursement amount",
                "Employee id",
                "Designation",
                "Department",
            ]
        )

        all_ride_exp = RideExpense.objects.filter(
            trip__id__in=expense_ids, trip__assigned_to__user__isnull=False
        )

        members = Member.objects.filter(
            id__in=all_ride_exp.values("trip__assigned_to__id")
        )

        # status_in_the_modal = {
        #     "pending_approval": 0,
        #     "pending_reimbursement": 0,
        #     "approval_rejected": 0,
        #     "reimbursement_rejected": 0,
        #     "reimbursed": 0,
        #     "closed": 0,
        # }

        all_member_details = get_ride_exp_report_data(all_ride_exp, members, org)

        # all_member_details = get_member_status_details(
        #     qs=objects,
        #     username_field="trip__assigned_to__user__id",
        #     status_field=status_in_the_modal,
        #     organization=org,
        # )
        for data in all_member_details:
            csv_data = [
                data["user"]["first_name"],
                data["user"]["last_name"],
                data["user"]["email"],
                data["pending_approval"],
                data["pending_reimbursement"],
                data["approval_rejected"],
                data["reimbursement_rejected"],
                data["reimbursed"],
                data["closed"],
                empty_or_data(extract_data_from_dict(data, ["total_ride_exp"])),
                empty_or_data(extract_data_from_dict(data, ["estimated_distance"])),
                empty_or_data(extract_data_from_dict(data, ["actual_distance"])),
                empty_or_data(extract_data_from_dict(data, ["reimbursement_amount"])),
                empty_or_data(extract_data_from_dict(data, ["member", "employee_id"])),
                empty_or_data(
                    extract_data_from_dict(data, ["member", "designation", "name"])
                ),
                empty_or_data(
                    extract_data_from_dict(data, ["member", "department", "name"])
                ),
            ]
            writer.writerow(csv_data)

    return filename


def export_member_trips_to_csv(
    export_request: ExportRequest, trip_ids: list, org
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"members_trips__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/members_trips/csv/"):
        os.makedirs("media/members_trips/csv/")
    with open(f"media/members_trips/csv/{filename}.csv", "w+") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "First name",
                "Last name",
                "Email",
                "Created",
                "Started",
                "Ended",
                "Cancelled",
                "Ride expense created",
                "Employee id",
                "Designation",
                "Department",
                "Total trips",
                "Start check in",
                "End check in",
                "Estimated KMs (Total)",
                "Actual KMs (Total)",
            ]
        )

        export_filters = export_request.filter
        start_date, end_date = None, None

        if isinstance(export_filters, dict):
            start_date = export_filters.get("start_date")
            end_date = export_filters.get("end_date")

            start_date = string_to_dt(start_date)
            end_date = string_to_dt(end_date)

        all_trips = Trip.objects.filter(
            id__in=trip_ids, assigned_to__user__isnull=False
        )
        members = Member.objects.filter(id__in=all_trips.values("assigned_to__id"))

        all_member_details = get_trip_report_data(
            all_trips, members, org, start_date, end_date
        )

        for data in all_member_details:
            # print(data)
            # print(extract_data_from_object(data, ["total_trips"]))
            # print(data["total_trips"])

            # print(extract_data_from_object(data, ["member", "employee_id"]))
            csv_data = [
                data["user"]["first_name"],
                data["user"]["last_name"],
                data["user"]["email"],
                data["created"],
                data["started"],
                data["ended"],
                data["cancelled"],
                data["ride_expense_created"],
                empty_or_data(extract_data_from_dict(data, ["member", "employee_id"])),
                empty_or_data(
                    extract_data_from_dict(data, ["member", "designation", "name"])
                ),
                empty_or_data(
                    extract_data_from_dict(data, ["member", "department", "name"])
                ),
                empty_or_data(extract_data_from_dict(data, ["total_trips"])),
                empty_or_data(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            extract_data_from_dict(data, ["start_check_in_dt"])
                        )
                    )
                ),
                empty_or_data(
                    remove_dt_millie_sec(
                        convert_dt_to_another_tz(
                            extract_data_from_dict(data, ["end_check_in_dt"])
                        )
                    )
                ),
                empty_or_data(extract_data_from_dict(data, ["estimated_distance"])),
                empty_or_data(extract_data_from_dict(data, ["actual_distance"])),
            ]
            # print(csv_data)
            # print("#################################################")

            writer.writerow(csv_data)

    return filename


def export_location_csv(export_request: ExportRequest, location_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"locations__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/locations/csv/"):
        os.makedirs("media/locations/csv/")
    with open(f"media/locations/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "name",
                "description",
                "latitude",
                "longitude",
                "radius",
                "source",
                "department",
            ]
        )

        locations = Location.objects.filter(id__in=location_ids)
        serializer = LocationSerializer(locations, many=True)

        for location in serializer.data:

            department_name = ""
            if location.get("department"):
                department_name = location.get("department", {}).get("name")

            data = [
                location.get("id"),
                location.get("name"),
                location.get("description"),
                location.get("latitude"),
                location.get("longitude"),
                location.get("radius"),
                location.get("source"),
                department_name,
            ]
            writer.writerow(data)

    return filename


def export_field_report_submission_csv(
    export_request: ExportRequest, submission_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"field_report_submission__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/field_report_submission/csv/"):
        os.makedirs("media/field_report_submission/csv/")
    with open(f"media/field_report_submission/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip name",
                "assigned to",
                "Department",
                "field_1",
                "field_2",
                "field_3",
                "field_4",
                "field_5",
                "field_6",
                "field_7",
                "field_8",
                "field_9",
                "field_10",
                "field_11",
                "field_12",
                "field_13",
                "field_14",
                "field_15",
                "field_16",
                "field_17",
                "field_18",
                "field_19",
                "field_20",
                "attachment",
            ]
        )

        submissions = FieldReportFormSubmissions.objects.filter(id__in=submission_ids)

        for submission in submissions:

            data = [
                extract_data_from_object(submission, ["trip", "name"]),
                extract_data_from_object(submission, ["trip", "assigned_to", "user", "email"]),
                extract_data_from_object(submission, ["department", "name"]),
            ]

            for field_name in FIELD_REPORT_FORM_CONFIG_FIELDS:
                field_data = extract_data_from_object(submission, [field_name])
                output = empty_or_data(convert_submission_data_to_str(field_data))
                data.append(output)
            
            field_report_file = submission.field_report_file.all()
            if field_report_file.exists():
                print(field_report_file)
                serialized_file_data = FieldReportFileSerializer(field_report_file, many=True).data

                file_urls = []

                sliced_ui_url = UI_DOMAIN_URL[:-1]

                for file_url in serialized_file_data:
                    full_url = sliced_ui_url + file_url.get("file")
                    file_urls.append(full_url)

                print(file_urls)
                if file_urls:
                    data.append(" && ".join(file_urls))


            writer.writerow(data)

    return filename


def export_admin_report_submission_csv(
    export_request: ExportRequest, submission_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"admin_report_submission__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/admin_report_submission/csv/"):
        os.makedirs("media/admin_report_submission/csv/")
    with open(f"media/admin_report_submission/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip name",
                "assigned to",
                "Department",
                "field_1",
                "field_2",
                "field_3",
                "field_4",
                "field_5",
                "field_6",
                "field_7",
                "field_8",
                "field_9",
                "field_10",
            ]
        )

        submissions = AdminReportFormSubmissions.objects.filter(id__in=submission_ids)

        for submission in submissions:

            data = [
                extract_data_from_object(submission, ["trip", "name"]),
                extract_data_from_object(submission, ["trip", "assigned_to", "user", "email"]),
                extract_data_from_object(submission, ["department", "name"]),
            ]

            for field_name in ADMIN_REPORT_CONFIG_FIELDS:
                field_data = extract_data_from_object(submission, [field_name])
                output = empty_or_data(convert_submission_data_to_str(field_data))
                data.append(output)

            writer.writerow(data)

    return filename


def export_create_trip_submission_csv(
    export_request: ExportRequest, submission_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"create_trip_submission__{file_suffix}"
    # check if folder exists
    # if not creat directory
    if not os.path.exists("media/create_trip_submission/csv/"):
        os.makedirs("media/create_trip_submission/csv/")
    with open(f"media/create_trip_submission/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "trip name",
                "assigned to",
                "Department",
                "field_1",
                "field_2",
                "field_3",
                "field_4",
                "field_5",
                "field_6",
                "field_7",
                "field_8",
                "field_9",
                "field_10",
            ]
        )

        submissions = CreateTripFormSubmissions.objects.filter(id__in=submission_ids)

        for submission in submissions:

            data = [
                extract_data_from_object(submission, ["trip", "name"]),
                extract_data_from_object(submission, ["trip", "assigned_to", "user", "email"]),
                extract_data_from_object(submission, ["department", "name"]),
            ]

            for field_name in CREATE_TRIP_FORM_CONFIG_FIELDS:
                field_data = extract_data_from_object(submission, [field_name])
                output = empty_or_data(convert_submission_data_to_str(field_data))
                data.append(output)

            writer.writerow(data)

    return filename
