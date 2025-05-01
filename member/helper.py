

from account.serializers import UserSerializer
from expense.models import RideExpense
from member.models import Member
from django.db.models import Q
from member.serializers import MemberSerializer, TempProfileSerializer

from django.db.models import FloatField
from django.db.models.functions import Cast
from django.db.models import Sum

import logging

from organization.models import Organization
from trip.models import Trip, TripDetails


logger = logging.getLogger(__name__)


# extract status count each user have from  trips and ride expense modal
# username_field is field for lookup username. qs have username username is the path
# status_field is the status include in the modal
def get_member_status_details(qs : "queryset", username_field: str, status_field: dict, organization: Organization) -> list:

    all_member_details = []
    member_details = {}
    count = 0
    member_qs = Member.objects.all()

    for data in qs:

        username = data[username_field]

        if not username in member_details:

            try:
                member = member_qs.filter(user__id=username).get()

                status_dict = status_field.copy() # othrewise this will pass reference
                status_dict["username"] = username
                status_dict["profile"] = TempProfileSerializer(member.profile, fields=["photo"]).data
                status_dict["user"] = UserSerializer(member.user).data

                all_member_details.append(status_dict)
                member_details[username] = count
                count += 1

            except Exception as e:
                logger.error(e)
            
        if  username in member_details:
            pos = member_details[username]
            member_status = all_member_details[pos]

            if data["status"] in member_status:
                member_status_count = member_status[data["status"]]
                member_status[data["status"]] = member_status_count + 1

    return all_member_details




def get_quarterly_report_of_the_year(trips_count_by_quarter: "queryset", type: str) -> list:
    """ Organize data using quarterly wise.
    """
    def get_corresponding_key(month):
        if month >= 1 and month <= 3:
            return "1-3"
        elif month >= 4 and month <= 6:
            return "4-6"
        elif month >= 7 and month <= 9:
            return "7-9"
        elif month >= 10 and month <= 12:
            return "10-12"
        

    result = {
        "1-3": 0,
        "4-6": 0,
        "7-9": 0,
        "10-12": 0,
    }

    for data in trips_count_by_quarter:
        # Using created month we can organize
        key = get_corresponding_key(data["created_at__month"])

        # Get count of data in every month.
        value = result[key]
        if type == "count":
            result[key]  = value + 1
        
        # Get reimbursement_amount sum of monthly
        if type == "sum" and data["reimbursement_amount"]:
            result[key]  = value + data["reimbursement_amount"]
        
    return result


# def get_member_status_details(qs : "queryset", username_field: str, status_field: dict, organization: Organization) -> list:

#     all_member_details = []
#     member_details = {}
#     count = 0
#     member_qs = Member.objects.all()

#     for data in qs:

#         username = data[username_field]

#         if not username in member_details:
            

#             try:
#                 member = member_qs.filter(user__id=username).get()

#                 status_dict = status_field.copy() # othrewise this will pass reference
#                 status_dict["username"] = username
#                 status_dict["profile"] = TempProfileSerializer(member.profile, fields=["photo"]).data
#                 status_dict["user"] = UserSerializer(member.user).data

#                 all_member_details.append(status_dict)
#                 member_details[username] = count
#                 count += 1

#             except Exception as e:
#                 logger.error(e)
            
#         if  username in member_details:
#             pos = member_details[username]
#             member_status = all_member_details[pos]

#             if data["status"] in member_status:
#                 member_status_count = member_status[data["status"]]
#                 member_status[data["status"]] = member_status_count + 1

#     return all_member_details


def get_trip_report_data(trips: Trip, members: Member, org:Organization, start_date=None, end_date=None) -> list:
    trip_details = TripDetails.objects.select_related("trip").filter(trip__organization=org)
    members = members.select_related("user").prefetch_related("profile")

    if start_date and end_date:
        trip_details = trip_details.filter(
            trip__created_at__date__gte=start_date.date(),
            trip__created_at__date__lte=end_date.date()
        )

    data = []
    for member in members:
        print("#############################################")
        print(member)
        
        member_trips = trips.filter(assigned_to=member)

        if not member_trips.exists():
            continue

        member_data = {
            "username": member.user.id,
            "profile": TempProfileSerializer(member.profile, fields=["photo"]).data,
            "member": MemberSerializer(member).data,
            "user": UserSerializer(member.user).data,
        }

        member_data["created"] = member_trips.filter(status="created").count()
        member_data["started"] = member_trips.filter(status="started").count()
        member_data["ended"] = member_trips.filter(status="ended").count()
        member_data["cancelled"] = member_trips.filter(status="cancelled").count()
        member_data["field_report_submitted"] = member_trips.filter(status="field_report_submitted").count()
        member_data["ride_expense_created"] = member_trips.filter(status="ride_expense_created").count()
        member_data["total_trips"] = member_trips.count()
        member_data["start_check_in_dt"] = None
        member_data["end_check_in_dt"] = None

        member_trip_details = trip_details.filter(trip__assigned_to=member)

        member_data["estimated_distance"] = member_trip_details.filter(
            trip__status__in=["ended", "ride_expense_created"]
        ).filter(
            ~Q(estimated_distance__exact='')
        ).filter(
            estimated_distance__isnull=False
        ).annotate(
            estimated_dis=Cast("estimated_distance", FloatField())
        ).aggregate(
            total_estimated_distance=Sum("estimated_dis")
        ).get("total_estimated_distance")

        member_data["actual_distance"] = member_trip_details.filter(
            trip__status="ride_expense_created"
        ).filter(
            ~Q(distance__exact='')
        ).filter(
            estimated_distance__isnull=False
        ).annotate(
            actual_dis=Cast("distance", FloatField())
        ).aggregate(
            total_actual_distance=Sum("actual_dis")
        ).get("total_actual_distance")

        check_in_trip_details_data = member_trip_details.filter(
            trip__status__in=["ended", "ride_expense_created"], end_scan__isnull=False
        )

        # last_check_in_trip_details_data = check_in_trip_details_data.order_by("end_scan__time").last()
        # print(last_check_in_trip_details_data)

        if check_in_trip_details_data.exists():
            member_check_in_out_data = check_in_trip_details_data
            if start_date and end_date:
 
                member_check_in_out_data = member_check_in_out_data.filter(
                    end_scan__time__date__gte=start_date.date(),
                    end_scan__time__date__lte=end_date.date()
                ).order_by("end_scan__time")
            else:
                last_user_scan = member_check_in_out_data.order_by(
                    "end_scan__time"
                ).last()
                if last_user_scan:
                    member_check_in_out_data = member_check_in_out_data.filter(
                        end_scan__time__date=last_user_scan.end_scan.time.date()
                    )
            if member_check_in_out_data.exists():
                member_data["start_check_in_dt"] = member_check_in_out_data.first().end_scan.time
                member_data["end_check_in_dt"] = member_check_in_out_data.last().end_scan.time

        # if last_check_in_trip_details_data:

        #     print(last_check_in_trip_details_data.end_scan)
        #     last_check_in_dt = last_check_in_trip_details_data.end_scan.time
        #     check_in_details_of_the_day = check_in_trip_details_data.filter(
        #         end_scan__time__date=last_check_in_dt.date()
        #     ).order_by("end_scan__time")

        #     if check_in_details_of_the_day.exists():
        #         member_data["start_check_in_dt"] = check_in_details_of_the_day.first().end_scan.time
        #         member_data["end_check_in_dt"] = check_in_details_of_the_day.last().end_scan.time

        data.append(member_data)

    return data


def get_ride_exp_report_data(all_ride_exp: RideExpense, members: Member, org: Organization):

    all_ride_exp = all_ride_exp.select_related("trip")
    members = members.select_related("user").prefetch_related("profile")

    all_trip_ids = all_ride_exp.values("trip__id")

    data = []
    trip_details = TripDetails.objects.filter(trip__organization=org, trip__id__in=all_trip_ids)
    for member in members:

        member_ride_exp = all_ride_exp.filter(trip__assigned_to=member)

        if not member_ride_exp.exists():
            continue

        member_data = {
            "username": member.user.id,
            "profile": TempProfileSerializer(member.profile, fields=["photo"]).data,
            "member": MemberSerializer(member).data,
            "user": UserSerializer(member.user).data,
        }

        member_data["pending_approval"] = member_ride_exp.filter(status="pending_approval").count()
        member_data["pending_reimbursement"] = member_ride_exp.filter(status="pending_reimbursement").count()
        member_data["approval_rejected"] = member_ride_exp.filter(status="approval_rejected").count()
        member_data["reimbursement_rejected"] = member_ride_exp.filter(status="reimbursement_rejected").count()
        member_data["reimbursed"] = member_ride_exp.filter(status="reimbursed").count()
        member_data["closed"] = member_ride_exp.filter(status="closed").count()
        member_data["total_ride_exp"] = member_ride_exp.filter(~Q(status="draft")).count()

        member_data["estimated_distance"] = trip_details.filter(
            trip__assigned_to=member, trip__status__in=["ended", "ride_expense_created"]
        ).filter(
            ~Q(estimated_distance__exact='')
        ).filter(
            estimated_distance__isnull=False
        ).annotate(
            estimated_dis=Cast("estimated_distance", FloatField())
        ).aggregate(
            total_estimated_distance=Sum("estimated_dis")
        ).get("total_estimated_distance")

        member_data["actual_distance"] = trip_details.filter(
            trip__assigned_to=member, trip__status="ride_expense_created"
        ).filter(
            ~Q(distance__exact='')
        ).filter(
            estimated_distance__isnull=False
        ).annotate(
            actual_dis=Cast("distance", FloatField())
        ).aggregate(
            total_actual_distance=Sum("actual_dis")
        ).get("total_actual_distance")

        member_data["reimbursement_amount"] = member_ride_exp.filter(
            reimbursement_amount__isnull=False
        ).aggregate(
            total_reimbursement_amount=Sum("reimbursement_amount")
        ).get("total_reimbursement_amount")

        data.append(member_data)
    return data
