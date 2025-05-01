from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api import permissions
from expense import serializers as expense_serializers
from expense.models import (
    RideExpense,
    RideExpenseStatus,
)
from expense.search import search_all_expenses, search_expenses
from expense.utils import (
    create_ride_expense_comment,
    get_payment_mode,
    get_ride_expense_by_trip,
)
from expense.email_funcs import (
    send_expense_update_notification,
    send_expense_notification_to_finance,
)
from expense.filter import filter_expenses, convert_query_params_to_dict

from trip import serializers as trip_serializers
from trip.models import Trip
from trip.utils import get_trip, has_access_to_trip
from utils import create_data, fetch_data, read_data
from export.utils import create_export_request

import logging


logger = logging.getLogger(__name__)


class MyApprovalsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = expense_serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        # If Admin
        if fetch_data.is_admin(member):
            # Get all expenses (except draft)
            expenses = RideExpense.objects.filter(Q(trip__organization=org) & Q(status__in=["pending_approval"]))

        # If Finance
        elif member.role == fetch_data.get_finance_role():
            expense_status = [
                *RideExpenseStatus.FINANCE_STAGE,
                *RideExpenseStatus.FINAL_STAGE,
            ]
            # Get all expenses in finance or final stage
            expenses = RideExpense.objects.filter(
                Q(trip__organization=org)
                & (Q(trip__assigned_to=member) | Q(trip__created_by=member))
                & Q(status__in=expense_status)
            )

        else:
            # Get all expenses belonging to the member/manager
            # If member, get all member's ride expenses.
            # If manager, get all non-draft ride expenses
            expenses = RideExpense.objects.filter(
                Q(trip__organization=org) & (Q(trip__assigned_to=member))
                | (Q(trip__assigned_to__manager=member) & ~Q(status="draft"))
            )

        filter_query = convert_query_params_to_dict(request.GET)
        expenses = filter_expenses(expenses, filter_query)

        search_query = request.GET.get("search")
        # expenses = search_expenses(expenses, search_query)
        expenses = search_all_expenses(expenses, search_query)
        

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


class ApprovalAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = expense_serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org.uuid, uuid)

        if has_access_to_trip(trip, member) is False:
            return read_data.get_403_response()

        ride_expense = get_ride_expense_by_trip(trip)
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        trip = get_trip(org.uuid, uuid)
        if trip is None:
            return read_data.get_404_response("Trip")

        logger.info(f"{trip.uuid}--{trip.name}--{member}")
        # BUG Update permissions for Finance
        # if has_access_to_trip(trip, member) is False:
        #     return read_data.get_403_response()

        ride_expense = get_ride_expense_by_trip(trip)
        if ride_expense is None:
            return read_data.get_404_response("Ride Expense")

        expense_status = request.data.get("status")
        comments = request.data.get("comments")
        reimbursement_amount = request.data.get("reimbursement_amount")
        payment_mode_uuid = request.data.get("payment_mode_uuid")

        # TODO LOW: Remove this later
        if expense_status == "approved":
            expense_status = "pending_reimbursement"

        if comments is None:
            return Response(
                {"message": "Comments need to be provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # * Manager Stage
        if ride_expense.status == "pending_approval":

            # If Rider has no manager, allow only admin users to edit status
            if ride_expense.trip.assigned_to.manager is None:
                if fetch_data.is_admin(member) is False:
                    return read_data.get_403_response("Only Admin can perform this action.")
            else:
                # If member is not rider's manager
                if ride_expense.trip.assigned_to.manager != member and fetch_data.is_admin(member) is False:
                    return read_data.get_403_response("Only rider's Manager/Admin can perform this action.")

            if expense_status not in RideExpenseStatus.MANAGER_STATUS_OPTIONS:
                return Response({"message": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

            ride_expense.approved_by = member

        # * Finance Stage
        elif ride_expense.status == "pending_reimbursement":

            # Only Finance can edit
            if fetch_data.is_finance(member) is False:
                return read_data.get_403_response("Only Finance can perform this action.")

            if expense_status not in RideExpenseStatus.FINANCE_STATUS_OPTIONS:
                return Response({"message": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
            ride_expense.reimbursed_by = member
        else:
            return read_data.get_403_response("Ride Expense cannot be edited at this stage")

        if comments:
            create_ride_expense_comment(ride_expense, expense_status, member, comments)

        if expense_status == "reimbursed":

            payment_mode = get_payment_mode(org.uuid, payment_mode_uuid)
            if payment_mode is None:
                return read_data.get_404_response("Payment Mode")

            ride_expense.payment_mode = payment_mode
            ride_expense.reimbursement_amount = reimbursement_amount

        ride_expense.status = expense_status
        try:
            ride_expense.save()
        except Exception as e:
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in ApprovalAPI")
            return Response({"message": "Unkown error occurred"}, status=status.HTTP_400_BAD_REQUEST)

        send_expense_update_notification(ride_expense)
        if ride_expense.status == "pending_reimbursement":
            send_expense_notification_to_finance(ride_expense)

        serializer = self.serializer_class(ride_expense)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyReimbursementsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = expense_serializers.RideExpenseAndTripSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role == fetch_data.get_member_role():
            return read_data.get_403_response("Only Admin/Finance can perform this action.")

        expense_status = [
            *RideExpenseStatus.FINANCE_STAGE,
            # reimbursed status
            RideExpenseStatus.FINAL_STAGE[0],
        ]
        # Get all expenses in finance or final stage
        expenses = RideExpense.objects.filter(Q(trip__organization=org) & Q(status__in=expense_status))

        filter_query = convert_query_params_to_dict(request.GET)
        expenses = filter_expenses(expenses, filter_query)

        search_query = request.GET.get("search")
        expenses = search_all_expenses(expenses, search_query)

        if bool(request.GET.get("export_csv", False)) is True:
            expense_ids = expenses.values_list("id", flat=True)
            export_request = create_export_request(member, "reimbursement_requests", list(expense_ids))
            if export_request is None:
                return Response({"export_request_uuid": None}, status=status.HTTP_404_NOT_FOUND)
            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)

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
