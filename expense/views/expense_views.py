from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.db.models import Q

from api import permissions

from expense.models import (
    RideExpense,
    RideExpenseDocs,
    RideExpenseComment,
    RideExpenseStatus,
)
from expense import serializers
from expense.filter import filter_expenses, convert_query_params_to_dict
from expense.search import search_expenses
from expense.email_funcs import (
    send_expense_creation_notification,
    send_expense_notification_to_finance,
)
from export.utils import create_export_request

from organization.models import Vehicle
from organization.utils import get_fuel, get_vehicle
from trip.search import search_all_ride_expeses, search_ride_expeses
from trip.utils import get_my_trip, get_trip, has_access_to_trip, round_off_value
from utils import read_data, fetch_data


import base64
import logging

from utils.response import HTTP_400


logger = logging.getLogger(__name__)


class AllRideExpensesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        lookup = Q(trip__organization=org) & ~Q(status="draft")

        # If not Admin
        if fetch_data.is_admin(member) is False:
            # Fetch Ride Expenses of Trips
            # 1. Assigned to me
            # 2. Assigned to my subordinates
            lookup &= Q(trip__assigned_to=member) | Q(trip__assigned_to__manager=member)

        # TODO MED: Fetch RideExpenses which have stage='draft' only if its created by me

        expenses = RideExpense.objects.filter(lookup)
        filter_query = convert_query_params_to_dict(request.GET)
        expenses = filter_expenses(expenses, filter_query)

        search_query = request.GET.get("search")
        # expenses = search_ride_expeses(expenses, search_query)
        expenses = search_all_ride_expeses(expenses, search_query)

        if bool(request.GET.get("export_csv", False)) is True:
            expense_ids = expenses.values_list("id", flat=True)
            export_request = create_export_request(member, "expense", list(expense_ids))
            if export_request:
                return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)
            return Response({"export_request_uuid": None}, status=status.HTTP_404_NOT_FOUND)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(expenses, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class RideExpenseAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org.uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """  Fill the expenses occur for the ride
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org.uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        ride_expense, created = RideExpense.objects.get_or_create(trip=trip)

        description = request.data.get("description")

        # * Trip Actual Distance
        actual_distance = request.data.get("actual_distance")
        if actual_distance is not None and actual_distance != "":

            try:
                actual_distance =  float(actual_distance)
            except ValueError:
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as err:
                print(err)
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)

            ride_expense.trip.trip_details.distance = actual_distance
            ride_expense.trip.trip_details.save()
        else:
            ride_expense.trip.trip_details.distance = None
            ride_expense.trip.trip_details.save()

        fuel_uuid = request.data.get("fuel_uuid")
        fuel = get_fuel(org_uuid, fuel_uuid)
        if fuel is None:
            return read_data.get_404_response("Fuel")

        vehicle_uuid = request.data.get("vehicle_uuid")
        vehicle = get_vehicle(org_uuid, vehicle_uuid)
        if fuel is None:
            return read_data.get_404_response("Vehicle")

        vehicle_mode = request.data.get("vehicle_mode")
        if vehicle_mode not in (x[0] for x in RideExpense.VEHICLE_MODE_CHOICES):
            return Response({"message": "Invalid Vehicle mode"}, status=status.HTTP_400_BAD_REQUEST)

        # Contain Fuel charge, tol charge , miscellaneous charge
        amount_breakdown = request.data.get("amount_breakdown")

        total_amount = 0
        for value in amount_breakdown.values():
            try:
                value = float(value)
            except Exception as e:
                logger.exception(f"Add exception for {e.__class__.__name__}" "in RideExpenseAPI")
                logger.error(e)
                value = 0

            total_amount += value

        claim_reimubrsement = request.data.get("claim_reimubrsement")

        ride_expense.description = description
        ride_expense.vehicle_mode = vehicle_mode
        ride_expense.fuel = fuel
        ride_expense.vehicle = vehicle
        ride_expense.amount = total_amount
        ride_expense.amount_breakdown = amount_breakdown
        ride_expense.claim_reimubrsement = claim_reimubrsement
        ride_expense.save()

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org.uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        if trip.assigned_to != member:
            return read_data.get_403_response("Only Rider can edit Ride Expense")

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        if ride_expense.status != "draft":
            return read_data.get_403_response("Only Ride Expense in draft stage can be edited")

        # * Trip Actual Distance
        actual_distance = request.data.get("actual_distance")
        if actual_distance is not None and actual_distance != "":

            try:
                actual_distance =  float(actual_distance)
            except ValueError:
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as err:
                print(err)
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)

            ride_expense.trip.trip_details.distance = actual_distance
            ride_expense.trip.trip_details.save()
        else:
            ride_expense.trip.trip_details.distance = None
            ride_expense.trip.trip_details.save()

        # * Fuel
        fuel_uuid = request.data.get("fuel_uuid")
        if fuel_uuid is not None:
            fuel = get_fuel(org_uuid, fuel_uuid)
            if fuel is None:
                return read_data.get_404_response("Fuel")
            ride_expense.fuel = fuel

        # * Vehicle
        vehicle_uuid = request.data.get("vehicle_uuid")
        if vehicle_uuid is not None:
            vehicle = get_vehicle(org_uuid, vehicle_uuid)
            if vehicle is None:
                return read_data.get_404_response("Vehicle")
            ride_expense.vehicle = vehicle

        # * Vehicle Mode
        vehicle_mode = request.data.get("vehicle_mode")
        if vehicle_mode is not None:
            if vehicle_mode not in (x[0] for x in RideExpense.VEHICLE_MODE_CHOICES):
                return Response(
                    {"message": "Invalid Vehicle mode"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ride_expense.vehicle_mode = vehicle_mode

        # * Amount
        amount_breakdown = request.data.get("amount_breakdown")
        if amount_breakdown is not None:
            total_amount = 0
            for value in amount_breakdown.values():
                try:
                    value = float(value)
                except Exception as e:
                    logger.exception(f"Add exception for {e.__class__.__name__}" "in RideExpenseAPI")
                    logger.error(e)
                    value = 0

                total_amount += value
            ride_expense.amount = total_amount
            ride_expense.amount_breakdown = amount_breakdown

        # * Claim Reimbursement
        claim_reimubrsement = request.data.get("claim_reimubrsement")
        if claim_reimubrsement is not None:
            ride_expense.claim_reimubrsement = claim_reimubrsement

        ride_expense.save()

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org.uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        if trip.assigned_to != member:
            return read_data.get_403_response("Only Rider can delete Ride Expense")

        ride_expense = trip.ride_expense
        if ride_expense.status != "draft":
            return Response(
                {"message": "Only Ride Expenses in draft stage can be deleted"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            ride_expense.delete()
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in RideExpenseAPI")
            return Response(
                {"message": "Failed to recall Ride Expense"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # CONFIRM: Manoj set trip status to 'ended'

        return read_data.get_200_delete_response("Ride Expense")


class RideExpenseDocsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseDocsSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        ride_expense_docs = ride_expense.ride_expense_docs.all()

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(ride_expense_docs, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """ Upload ride expenses deails.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        documents = request.data.get("documents")
        images = request.data.get("images")

        for document in documents:

            try:
                document = ContentFile(base64.b64decode(document), name="temp." + "pdf")
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in RideExpenseDocsAPI")
                return Response({"message": "Invalid document"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                RideExpenseDocs.objects.create(ride_expense=ride_expense, document=document)
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in RideExpenseDocsAPI")

        for image in images:
            try:
                image = ContentFile(base64.b64decode(image), name="temp." + "png")
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in RideExpenseDocsAPI")
                return Response({"message": "Invalid image"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                RideExpenseDocs.objects.create(ride_expense=ride_expense, image=image)
            except Exception as e:
                logger.error(e)
                logger.exception(f"Add exception for {e.__class__.__name__} in RideExpenseDocsAPI")

        # ride_expense_doc = RideExpenseDocs.objects.create(
        #     ride_expense=ride_expense, document=document, image=image
        # )

        if ride_expense.status in RideExpenseStatus.FINAL_STAGE:
            return Response(
                {"message": "Cannot add documents once Ride Expense is finalized"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # if ride_expense.status == "draft":
        #     ride_expense.status = "pending_approval"
        #     ride_expense.save()

        ride_expense_docs = ride_expense.ride_expense_docs.all()
        serializer = self.serializer_class(ride_expense_docs, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org_uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        uuid = request.data.get("ride_expense_doc_uuid")
        ride_expense_doc = ride_expense.ride_expense_docs.filter(uuid=uuid).first()
        if ride_expense_doc is None:
            return read_data.get_404_response("Ride Expense Document")

        if ride_expense.status in RideExpenseStatus.FINAL_STAGE:
            return Response(
                {"message": "Cannot remove documents once Ride Expense is finalized"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ride_expense_doc.delete()

        return Response({"message": "Successfully deleted document"}, status=status.HTTP_200_OK)


class RecallRideExpensesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseAndTripSerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org.uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        if trip.assigned_to != member:
            return read_data.get_403_response("Only Rider can create Ride Expense")

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        if ride_expense.status == "reimbursed":
            return Response(
                {"message": "Cannot recall reimbursed Ride Expenses"},
                status=status.HTTP_403_FORBIDDEN,
            )

        ride_expense.status = "draft"
        ride_expense.save()

        # CONFIRM Manoj: Will trip's status be set to 'ended'
        ride_expense.trip.status = "ended"
        ride_expense.trip.save()

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubmitRideExpenseAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RideExpenseAndTripSerializer

    def post(self, request, *args, **kwargs):
        """ Save ride exp as draft
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_my_trip(org.uuid, uuid, member)
        if trip is None:
            return read_data.get_404_response("Trip")

        trip_curr_status = trip.status

        if trip_curr_status not in ("ended", "field_report_submitted"):
            return HTTP_400(
                f"Trip with {trip_curr_status} status cannot create ride expense."
            )
        
        member_department = member.department
        if member_department:
            department_field_report = member_department.enable_field_report

            if department_field_report is True and trip_curr_status != "field_report_submitted":
                return HTTP_400(
                    "Please submit the field report before creating ride expense."
                )        

        if trip.assigned_to != member:
            return read_data.get_403_response("Only Rider can submit Ride Expense")

        ride_expense = trip.ride_expense
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        if ride_expense.status != "draft":
            return read_data.get_403_response("Only Ride Expense in draft stage can be submitted")

        # * Trip Actual Distance
        actual_distance = request.data.get("actual_distance")
        if actual_distance is not None and actual_distance != "":

            try:
                actual_distance =  float(actual_distance)
            except ValueError:
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as err:
                print(err)
                return Response({"message": "Please enter valid actual distance."}, status=status.HTTP_400_BAD_REQUEST)

            ride_expense.trip.trip_details.distance = actual_distance
            ride_expense.trip.trip_details.save()
        else:
            ride_expense.trip.trip_details.distance = None
            ride_expense.trip.trip_details.save()

        # * Fuel
        fuel_uuid = request.data.get("fuel_uuid")
        if fuel_uuid is not None:
            fuel = get_fuel(org_uuid, fuel_uuid)
            if fuel is None:
                return read_data.get_404_response("Fuel")
            ride_expense.fuel = fuel

        # * Vehicle
        vehicle_uuid = request.data.get("vehicle_uuid")
        if vehicle_uuid is not None:
            vehicle = get_vehicle(org_uuid, vehicle_uuid)
            if vehicle is None:
                return read_data.get_404_response("Vehicle")
            ride_expense.vehicle = vehicle

        # * Vehicle Mode
        vehicle_mode = request.data.get("vehicle_mode")
        if vehicle_mode is not None:
            if vehicle_mode not in (x[0] for x in RideExpense.VEHICLE_MODE_CHOICES):
                return Response(
                    {"message": "Invalid Vehicle mode"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ride_expense.vehicle_mode = vehicle_mode

        # * Amount
        amount_breakdown = request.data.get("amount_breakdown")
        if amount_breakdown is not None:
            total_amount = 0
            for value in amount_breakdown.values():
                try:
                    value = float(value)
                except Exception as e:
                    logger.exception(f"Add exception for {e.__class__.__name__}" "in RideExpenseAPI")
                    logger.error(e)
                    value = 0

                total_amount += value
            ride_expense.amount = round_off_value(total_amount)
            ride_expense.amount_breakdown = amount_breakdown

        # * Document Check
        if ride_expense.vehicle_mode == "hire":
            if ride_expense.ride_expense_docs.count() == 0:
                return Response(
                    {"message": ("Ride Expenses with vehicle mode " "set to 'hire' requires documents")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        # * Claim Reimbursement
        claim_reimubrsement = request.data.get("claim_reimubrsement")
        if claim_reimubrsement is not None:
            ride_expense.claim_reimubrsement = claim_reimubrsement

        # if claim reimbursement is false
        if claim_reimubrsement is not None and claim_reimubrsement is False:
            # set status closed
            ride_expense.status = "closed"
            # set auto approved = true
            ride_expense.auto_approved = True
            ride_expense.save()

        # * Auto Approval Limit
        # Vehicle have special amt limit. If exp is less than the limit they dont need confirmation from
        # finance team. is mandatory_approval is True approval is required.
        if (
            ride_expense.vehicle.auto_approval_limit is not None
            and ride_expense.amount <= ride_expense.vehicle.auto_approval_limit
            and org.settings.get("mandatory_approval") is False
        ):
            ride_expense.status = "pending_reimbursement"
            ride_expense.auto_approved = True
            ride_expense.save()
            send_expense_notification_to_finance(ride_expense)
        else:
            ride_expense.status = "pending_approval"
            ride_expense.save()
            send_expense_creation_notification(ride_expense)

        ride_expense.trip.status = "ride_expense_created"
        ride_expense.trip.save()

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)
