from calendar import c
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Sum, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from account.models import User
from account.serializers import UserSerializer
from expense.filter import filter_expenses
from export.utils import create_export_request
from trip.search import search_ride_expeses, search_trips
from utils.fetch_data import get_user_and_profile_data
from member.helper import get_member_status_details, get_quarterly_report_of_the_year, get_ride_exp_report_data, get_trip_report_data
from api import permissions
from django.db.models import F

from expense.models import RideExpense

from member.models import Member
from member import search, serializers
from datetime import datetime
from organization.models import Designation, Organization, Role
from trip.models import Trip, TripDetails, TripScan
from trip.filter import convert_query_params_to_dict, filter_trips

from utils import create_data, email_funcs, fetch_data, read_data

import csv
import pandas as pd
import logging


logger = logging.getLogger(__name__)


class StatisticsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        member = fetch_data.get_member(request.user, org.uuid)
        date = request.GET.get("date")

        if date:
            date = create_data.convert_string_to_datetime(date)
            if date is None:
                return Response(
                    {"message": "Invalid date format. Send it as '%yyyy-%mm-%dd'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            date = read_data.get_current_datetime()

        if member.role == fetch_data.get_member_role():

            completed_trips = TripDetails.objects.filter(
                (Q(trip__assigned_to=member) | Q(trip__assigned_to__manager=member))
                & Q(end_scan__isnull=False)
                & Q(end_time__date=date)
            ).count()

            pending_approvals = RideExpense.objects.filter(
                (Q(trip__assigned_to=member) | Q(trip__assigned_to__manager=member)) & Q(status="pending_approval")
            ).count()

            data = {
                "completed_trips": completed_trips,
                "pending_approvals": pending_approvals,
            }

        else:
            completed_trips = TripDetails.objects.filter(
                Q(end_scan__isnull=False) & Q(end_time__date=date) & Q(trip__organization=org)
            ).count()
            pending_approvals = RideExpense.objects.filter(
                Q(status="pending_approval") & Q(trip__organization=org)
            ).count()
            pending_reimbursements = RideExpense.objects.filter(
                Q(status="pending_reimbursement") & Q(trip__organization=org)
            ).count()

            data = {
                "completed_trips": completed_trips,
                "pending_approvals": pending_approvals,
                "pending_reimbursements": pending_reimbursements,
            }

        return Response(
            data,
            status=status.HTTP_200_OK,
        )


class ReportAPI(views.APIView):
    """ Admin only view """

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        # * Rider Performance
        """
        Top 3 riders with most number of rides in a given date range
        And filter on Department, All, Date range, Person, Org
        Ride Report Allow this Ride report to Download in CSV or Excel Format
        """
        rider_performance_list = []

        rider_count = request.GET.get("rider_count", 3)
        rider_performance = (
            trips.filter(status__in=["ended", "ride_expense_created"])
            .values("assigned_to")
            .annotate(rides=Count("assigned_to"))
            .order_by("-rides")[:rider_count]
        )

        for data in rider_performance:
            member_id = data.get("assigned_to")
            rides = data.get("rides")

            try:
                member = Member.objects.get(id=member_id)
            except Member.DoesNotExist as e:
                logger.error(e)
                continue

            serializer = serializers.MemberSerializer(member)
            rider_performance_list.append({"member": serializer.data, "rides": rides})

        # * Status Pie Chart
        trip_status_dict = {}
        trip_status_values = trips.values("status").annotate(count=Count("status"))

        for trip_status in trip_status_values:
            trip_status_name = trip_status.get("status")
            trip_status_count = trip_status.get("count")
            trip_status_dict[trip_status_name] = trip_status_count

        # * Basic statistics

        completed_trips = trips.filter(status="ride_expense_created")
        ride_expenses = RideExpense.objects.filter(trip__in=completed_trips)
        total_amount_to_be_reimbursed = ride_expenses.aggregate(Sum("amount"))
        total_amount_reimbursed = ride_expenses.filter(status="reimbursed").aggregate(Sum("reimbursement_amount"))

        basic_stats = {
            "total_amount_to_be_reimbursed": total_amount_to_be_reimbursed,
            "amount_reimbursed": total_amount_reimbursed,
        }

        report_response = {
            "rider_performance": rider_performance_list,
            "trip_status": trip_status_dict,
            "basic_stats": basic_stats,
        }
        return Response(report_response, status=status.HTTP_200_OK)


class MemberReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)
        trips = filter_trips(trips, filter_query)

        member_ids = trips.values_list("assigned_to__id", flat=True)
        members = Member.objects.filter(id__in=member_ids)

        member_report = {}
        for member in members:

            total_trips = trips.filter(assigned_to=member)
            completed_trips = total_trips.filter(status__in=["ended", "ride_expense_created"])

            if total_trips > 0:
                completion_rate = (completed_trips / total_trips) * 100
            else:
                completion_rate = 0

            expensed_trips = trips.filter(status="ride_expense_created")
            ride_expenses = RideExpense.objects.filter(Q(trip__in=expensed_trips) & Q(claim_reimbursement=True))

            total_amount_claimed = ride_expenses.aggregate(Sum("amount")).get("amount__sum")
            total_amount_approved = (
                ride_expenses.filter(status="reimbursed").aggregate(Sum("amount")).get("amount__sum")
            )
            total_amount_rejected = (
                ride_expenses.filter(status="reimbursement_rejected").aggregate(Sum("amount")).get("amount__sum")
            )

            member_report[member.email] = {
                "completion_rate": completion_rate,
                "total_amount_claimed": total_amount_claimed,
                "total_amount_approved": total_amount_approved,
                "total_amount_rejected": total_amount_rejected,
            }

        report_response = {"member_report": member_report}
        return Response(report_response, status=status.HTTP_200_OK)


class DashboardAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = None

    def get_reimbersement_count_and_amount(self, org : Organization) ->  dict:
        ride_expense_calc = RideExpense.objects.filter(
            Q(trip__organization=org) & Q(status="reimbursed")   
        ).values(
            "updated_at__month", 
            "updated_at__year", 
            "reimbursement_amount"
        ).filter(
            updated_at__month=datetime.now().month,
            updated_at__year=datetime.now().year
        )

        return {
            "approved_reimbursement_count": ride_expense_calc.count(),
            "total_reimbursement_amount": ride_expense_calc.aggregate(
                Sum("reimbursement_amount"))["reimbursement_amount__sum"]
        }

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        member_is_admin = fetch_data.is_admin(member)
        member_is_finance = fetch_data.is_finance(member)
        member_is_manager = member.managed_members.all().count() > 1


        # If Admin
        if member_is_admin:

            ride_expenses = RideExpense.objects.filter(
                Q(trip__organization=org)
            )

            reimbursed_expenses = RideExpense.objects.filter(
                Q(trip__organization=org) & Q(status="reimbursed")
            ).count()

            stats = {
                "reimbursed_expenses": reimbursed_expenses,
                "pending_approval": ride_expenses.filter(
                    status="pending_approval").count(),
                "pending_reimbursement": ride_expenses.filter(
                    status="pending_reimbursement").count(),
            }

        else:

            if member_is_finance:

                pending_reimbursements = RideExpense.objects.filter(
                    Q(trip__organization=org) & Q(status="pending_reimbursement")   
                ).count()


                reimbursed_expenses = RideExpense.objects.filter(
                    Q(trip__organization=org) & Q(status="reimbursed")
                )

                stats = {
                    "pending_reimbursements": pending_reimbursements,
                    "reimbursed_expenses": reimbursed_expenses.count(),
                }

            else:

                pending_expenses = RideExpense.objects.filter(
                    Q(trip__assigned_to=member) & Q(status__in=["pending_approval", "pending_reimbursement"])
                ).count()

                stats = {
                    "pending_expenses": pending_expenses,
                }

        # If Manager
        if member_is_manager:

            trips_completed_by_team = Trip.objects.filter(
                Q(assigned_to__manager=member)
                & Q(status__in=["ended", "ride_expense_created"])   
            ).count()

            managed_members_stats = {
                "trips_completed_by_team": trips_completed_by_team,
            }
            stats.update({"managed_members": managed_members_stats})
        
        if member_is_finance or member_is_admin:
            stats.update(self.get_reimbersement_count_and_amount(org))
            

        # pending approval of the subordinated
        if (member_is_manager or member_is_finance) and not member_is_admin:
            pending_approval = RideExpense.objects.filter(
                Q(trip__assigned_to__manager=member)
                & Q(status="pending_approval")
            ).count()
            stats["pending_approval"] = pending_approval

        
        # ==== As a Member ====
        # last scan time if user have a last scan
        last_scan = (
            TripScan.objects.filter(
                Q(end_trip_details__trip__assigned_to=member)
                | 
                Q(start_trip_details__trip__assigned_to=member)
            )
            .order_by("-time")
            .first()
        )


        # my pending ride expenses count 
        my_pending_ride_expenses = RideExpense.objects.filter(
            Q(trip__assigned_to=member)
            & Q(status__in=["pending_approval", "pending_reimbursement"])
        ).count()


        # total trips completed as a member
        total_trips_completed = Trip.objects.filter(
            Q(assigned_to=member)
            & Q(status__in=["ended", "ride_expense_created"])
        ).count()

        stats["last_scan_time"] = last_scan.time if last_scan else None
        stats["my_pending_ride_expenses_count"] = my_pending_ride_expenses
        # stats["total_trips_completed"] = total_trips_completed
        stats["trips_completed"] = total_trips_completed


        return Response({"stats": stats}, status=status.HTTP_200_OK)


class AllTripTopRidersAPI(views.APIView):
    permission_classes = [IsAuthenticated]

    # get (user details) data from profile and user modal
    def get_rider_details(self, riders):
        user_deials = []

        rider_id = []
        rider_with_count = {}
        for rider in riders:
            rider_id.append(rider["assigned_to"])
            rider_with_count[rider["assigned_to"]] = rider["count"]

        members = Member.objects.select_related(
                "user"
            ).prefetch_related(
                "profile"
            ).filter(id__in=rider_id)

        for member in members:
            temp = {}
            try:
                profile = serializers.TempProfileSerializer(member.profile).data
                temp["count"] = rider_with_count[member.id]
                temp["profile"] = profile
                temp["user_details"] = {
                    "username": member.user.username,
                    "first_name": member.user.first_name,
                    "last_name" : member.user.last_name,
                    "email": member.user.email
                }
                user_deials.append(temp)
            except Member.DoesNotExist as e:
                logger.error(e)

        return user_deials

    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        trips = filter_trips(trips, filter_query)

        # top user assigned to count and user
        top_riders_assigned = trips.values( 
            "assigned_to"
        ).annotate(count=Count("assigned_to")).order_by("-count")[:3]

        # top 3 user have completion rate
        top_riders_completed = trips.filter(
            status__in=["ended", "ride_expense_created"]
        ).values("assigned_to").annotate(
            count=Count("assigned_to")).order_by("-count")[:3]


        rider_data = [
            {"assigned_to": get_user_and_profile_data(top_riders_assigned)},
            {"completed": get_user_and_profile_data(top_riders_completed)},
        ]

        return Response(rider_data, status=status.HTTP_200_OK)


class AllTripStatistics(views.APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        trips = filter_trips(trips, filter_query)

        status_count = trips.values("status").annotate(count=Count("status"))

        datas = {
            "count_of_status": status_count,
        }
        return Response(datas, status=status.HTTP_200_OK)



class  AllTripsMemberDetails(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        trips = filter_trips(trips, filter_query)

        search_query = request.GET.get("search", None)
        trips = search_trips(trips, search_query)

        all_trips = trips.filter(
            assigned_to__user__isnull=False
        ).order_by("assigned_to__id")

        member_ids = all_trips.values("assigned_to__id")
        members = org.members.filter(id__in=member_ids)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        members = page_obj.object_list
    
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if start_date:
            start_date = read_data.string_to_dt(start_date)
        if end_date:
            end_date = read_data.string_to_dt(end_date)
        all_member_details = get_trip_report_data(all_trips, members, org, start_date, end_date)


        # TODO add pagination as function
        # per_page = request.GET.get("per_page", 10)
        # page = request.GET.get("page", 1)
        # paginator = Paginator(all_member_details, per_page)
        # page_obj = paginator.get_page(page)
        # all_trips = page_obj.object_list
        # print(page_obj.object_list)

        return Response(
            {
                "data": all_member_details,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK
        )


class AllRideExpensesStatistics(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        all_ride_exp = RideExpense.objects.filter(
            trip__assigned_to__organization=org
        )

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        all_ride_exp = filter_expenses(all_ride_exp, filter_query)

        # ride_expense status and count
        status_and_count = all_ride_exp.values(
            "status", 
        ).annotate(count=Count("status"))


        datas = {   
            "count_of_status": status_and_count,
        }
        return Response(datas, status=status.HTTP_200_OK)

class AllRideExpensesTopReimbersement(views.APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        # reimbursed completed members
        all_ride_exp = RideExpense.objects.filter(
            status="reimbursed",
            trip__assigned_to__organization=org
        )

        filter_query = convert_query_params_to_dict (request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        all_ride_exp = filter_expenses(all_ride_exp, filter_query)

        all_ride_exp = all_ride_exp.values(
            "trip__assigned_to"
        ).annotate(
            count=Count("trip__assigned_to"),
            assigned_to=F("trip__assigned_to")
        ).order_by("-count")[:3]
        data = get_user_and_profile_data(all_ride_exp)

        return Response(data, status=status.HTTP_200_OK)




class AllRideExpensesMemberDetails(views.APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        filter_query = convert_query_params_to_dict (request.GET)
        rider_exp = RideExpense.objects.filter(
            trip__assigned_to__organization=org,
            trip__status__in=["ended", "ride_expense_created"]
        )            

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        rider_exp = filter_expenses(rider_exp, filter_query)

        all_ride_exp = rider_exp.filter(
            trip__assigned_to__user__isnull=False
        ).exclude(
            status="draft"
        ).order_by(
            "trip__assigned_to__id"
        )

        member_ids = all_ride_exp.values("trip__assigned_to__id")
        members = org.members.filter(id__in=member_ids)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(members, per_page)
        page_obj = paginator.get_page(page)
        members = page_obj.object_list

        all_member_details = get_ride_exp_report_data(all_ride_exp, members, org)


        # all_member_details = get_member_status_details(
        #     qs = all_ride_exp, 
        #     username_field="trip__assigned_to__user__id",
        #     status_field=status_in_the_modal,
        #     organization=org
        # )

        # per_page = request.GET.get("per_page", 10)
        # page = request.GET.get("page", 1)
        # paginator = Paginator(all_member_details, per_page)
        # page_obj = paginator.get_page(page)
        # all_member_details = page_obj.object_list
        
        return Response(
            {
                "data": all_member_details,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            }, 
            status=status.HTTP_200_OK
        )

    


class AllRideExpensesMemberDetailsCSV(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        filter_query = convert_query_params_to_dict (request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        rider_exp = RideExpense.objects.filter(
            trip__assigned_to__organization=org,
            trip__status__in=["ended", "ride_expense_created"]
        )


        search_query = request.GET.get("search", None)
        rider_exp = search_ride_expeses(rider_exp, search_query)

        rider_exp = filter_expenses(rider_exp, filter_query)
        all_ride_exp = rider_exp.filter(
            trip__assigned_to__user__isnull=False
        ).exclude(
            status="draft"
        ).values_list(
            "trip__id", flat=True
        ).order_by(
            "trip__assigned_to__id"
        )

        rmv_duplicate = set(all_ride_exp)

        export_request = create_export_request(member, "members_ride_expense", list(rmv_duplicate))
        if export_request:
            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)
        else:
            return Response({"export_request_uuid": None}, status=status.HTTP_404_NOT_FOUND)


class AllRideExpensesMemberDetailsByYearly(views.APIView):
    permission_classes = [IsAuthenticated]        

    def get(self, request):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        all_ride_exp = RideExpense.objects.filter(trip__assigned_to__organization=org)
        print(all_ride_exp)

        filter_query = convert_query_params_to_dict (request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        all_ride_exp = filter_expenses(all_ride_exp, filter_query)

        year = request.GET.get("year", datetime.now().year)
        if not year:
            year = datetime.now().year


        # reimbursed_count within quarter 
        reimbursed_count = all_ride_exp.filter(
            status="reimbursed",
            created_at__year=year
        ).values(
            "created_at__month", "reimbursement_amount"
        )
        print(f"reimbursed_count: {reimbursed_count}")
        reimbursed_count = get_quarterly_report_of_the_year(reimbursed_count, "sum")
    
        datas = {   
            "year": year,
            "years_avillable": all_ride_exp.values_list("created_at__year", flat=True).distinct().order_by("-created_at__year"),
            "reimbursed_by_quarter_and_count": reimbursed_count
        }
        return Response(datas, status=status.HTTP_200_OK)



class AllTripsMemberDetailsByYearly(views.APIView):
    permission_classes = [IsAuthenticated]        

    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        
        trips = org.trips.all()

        filter_query = convert_query_params_to_dict(request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        trips = filter_trips(trips, filter_query)

        year = datetime.now().year
        if "year" in request.GET and request.GET.get("year"):
            year = request.GET.get("year")


        trips_count_by_quarter = trips.filter(
            created_at__year= year
        ).values(
            "created_at__month", 
        )

        trips_count_by_quarter = get_quarterly_report_of_the_year(trips_count_by_quarter, "count")

        datas = {   
            "year": year,
            "years_avillable": trips.values_list("created_at__year", flat=True).distinct().order_by("-created_at__year"),
            "total_trip_by_quarter": trips_count_by_quarter
        }
        return Response(datas, status=status.HTTP_200_OK)



class AllTripMemberDetailsCSV(views.APIView):


    def get(self, request):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org_uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()


        trips = org.trips.all()

        filter_query = convert_query_params_to_dict (request.GET)

        if "organization_location" in filter_query and isinstance(filter_query.get("organization_location"), list):
            filter_query["organization_location_uuids"] = filter_query["organization_location"]

        trips = filter_trips(trips, filter_query)

        
        search_query = request.GET.get("search", None)
        trips = search_trips(trips, search_query)

        all_trips = trips.filter(
            assigned_to__user__isnull=False
        ).values_list(
            "id", flat=True
        ).order_by("assigned_to__id")

        rmv_duplicate = set(all_trips)

        export_request = create_export_request(member, "members_trips", list(rmv_duplicate))
        if export_request:
            
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            export_request.filter = {
                "start_date": start_date,
                "end_date": end_date,
            }
            export_request.save()

            return Response({"export_request_uuid": export_request.uuid}, status=status.HTTP_200_OK)
        return Response({"export_request_uuid": None}, status=status.HTTP_404_NOT_FOUND)
