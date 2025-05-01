# org_deletion.py


"""
Description:
This script is designed to delete an organization and all associated data. It verifies the existence of the organization 
using the provided UUID, systematically deletes trips, members, payments, and the organization itself. The script prompts 
for confirmation before proceeding with deletion.

Flow:
1. Initiate the organization deletion process by providing the unique UUID of the desired organization.
2. Verify the existence of the organization using the provided UUID. If not found, an error message is displayed.
3. Prompt the user for confirmation before proceeding with deletion.
4. Delete trips associated with the organization, including trip details, scans, and associated objects.
5. Delete organization members and users.
6. Delete payment objects associated with the organization.
7. Finally, delete the organization.

Note: Error handling is implemented using try-except blocks to catch and display errors in the terminal.
"""

# Rest of the script follows...

import json
import os
import sys
# importing validation error for error handling
from django.core.exceptions import ValidationError

# importing models from all apps
from account.models import User, SessionToken, AuthToken
from expense.models import (
    RideExpense,
    RideExpenseComment,
    RideExpenseDocs,
    RideExpenseStatus,
    PaymentMode,
)
from form_builder.models import (
    FieldReportFile,
    FieldReportFormConfig,
    FieldReportFormSubmissions,
    CreateTripFormConfig,
    CreateTripFormSubmissions,
    AdminReportFormConfig,
    AdminReportFormSubmissions,
)
from member.models import Member, Profile, MemberImage
from organization.models import (
    Organization,
    Vehicle,
    Fuel,
    RideExpenseCostMatrix,
    Location,
    Department,
    Designation,
    OrganizationLocation,
    ExternalConnection,
)
from trip.models import Trip, TripTemplate, TripDetails, TripEstimation, TripScan


import os
import sys

def style_error(message):
    """Returns an error message in red."""
    return f"\033[91m{message}\033[0m\n"

def style_success(message):
    """Returns a success message in green."""
    return f"\033[92m{message}\033[0m\n"

def style_warning(message):
    """Returns a warning message in yellow."""
    return f"\033[93m{message}\033[0m\n"





# Function to delete organization and associated data
def delete_organization():
    """Function to delete organization and associated data"""
    sys.stdout.write(style_success("Executing organization deletion command....."))
    
    try:
        # receiving organization uuid from user
        uuid = input(">>> Enter organization uuid for delete: ")

        # query for retrieve organization from db with error handling
        try:
            organization_instance = Organization.objects.get(uuid=uuid)
        except Organization.DoesNotExist:
            sys.stdout.write(style_error("Error: Organization not found in database with the above uuid"))
            return
        except Exception as e:
            sys.stdout.write(style_error(f"Error: {e}"))
            return

        sys.stdout.write(style_warning(f"Organization found: {organization_instance.name}"))

        print("\n")

        # Prompt user for confirmation
        sys.stdout.write(style_warning(
            "Note: all of your data and documents associated with this organization will permanently remove"
        ))
        print("\n")
        confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            return

        # Retrieve trips associated with the organization
        trips = Trip.objects.filter(organization=organization_instance)

        trip_org_name = trips.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete trips and associated models under organization :{trip_org_name}"))
        trip_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if trip_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()


        # iteration through trips to delete data associated with trip
        for trip in trips:
          
            try:
                trip_details = TripDetails.objects.get(trip=trip, trip__organization=organization_instance)
            except TripDetails.DoesNotExist:
                continue
            

            # iterate through trip details to find trip scans and delete
            # TODO remove for loop. Take the code to the outside block.
            
            start_scan = trip_details.start_scan
            end_scan = trip_details.end_scan

                # deleting start scan and image from db if found
            if start_scan:
                if start_scan.image and os.path.exists(start_scan.image.path):
                    os.remove(start_scan.image.path)

                start_scan.delete()

                # deleting end scan and image from db if found
                if end_scan:
                    if end_scan.image and os.path.exists(end_scan.image.path):
                        os.remove(end_scan.image.path)

                    end_scan.delete()

                # deleting trip details
            trip_details.delete()

            # trip estimation deletion
            # trip_estimation = None
            # try:
            #     trip_estimation = TripEstimation.objects.get(trip=trip)
            # except TripEstimation.DoesNotExist:
            #     pass

            # if trip_estimation is not None:
            #     trip_estimation.delete()

            # Delete instances from RideExpense, RideExpenseComment, RideExpenseDocs, and PaymentMode models
      
            ride_expenses = RideExpense.objects.filter(
                trip=trip, trip__organization=organization_instance
            )

            _name_of_org = ride_expenses.order_by("trip__organization__name").values("trip__organization__name").distinct()
            sys.stdout.write(style_warning(f"you are about to delete ride_expenses :{_name_of_org}"))
            # trip_confirmation = input(
            #     ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
            # )
            # print("\n")
            # if trip_confirmation.lower() != "yes":
            #     sys.stdout.write(style_error("Deletion aborted."))
            #     sys.exit()

            # TODO @shahin verify
            ride_expense_comments = RideExpenseComment.objects.filter(
                ride_expense__trip=trip, ride_expense__trip__organization=organization_instance
            )

            _name_of_org = ride_expense_comments.order_by("ride_expense__trip__organization__name").values("ride_expense__trip__organization__name").distinct()
            sys.stdout.write(style_warning(f"you are about to delete ride_expense_comments :{_name_of_org}"))
            # trip_confirmation = input(
            #     ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
            # )
            # print("\n")
            # if trip_confirmation.lower() != "yes":
            #     sys.stdout.write(style_error("Deletion aborted."))
            #     sys.exit()

            ride_expense_docs = RideExpenseDocs.objects.filter(
                ride_expense__trip=trip, ride_expense__trip__organization=organization_instance
            )

            _name_of_org = ride_expense_docs.order_by("ride_expense__trip__organization__name").values("ride_expense__trip__organization__name").distinct()
            sys.stdout.write(style_warning(f"you are about to delete ride_expense_docs :{_name_of_org}"))
            # trip_confirmation = input(
            #     ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
            # )
            # print("\n")
            # if trip_confirmation.lower() != "yes":
            #     sys.stdout.write(style_error("Deletion aborted."))
            #     sys.exit()

            # deleting ride expenses documents and images
            for ride_expense_doc in ride_expense_docs:
                if ride_expense_doc.document:
                    if os.path.exists(ride_expense_doc.document.path):
                        os.remove(ride_expense_doc.document.path)
                if ride_expense_doc.image:
                    if os.path.exists(ride_expense_doc.image.path):
                        os.remove(ride_expense_doc.image.path)
                ride_expense_doc.delete()
            ride_expense_comments.delete()
            ride_expenses.delete()

            # trip status have to change, deletion is not possible in the case of status is created
            trip.status = "cancelled"
            trip.save()

        # deletion of trip templates in organization
        # trip_templates = TripTemplate.objects.filter(organization=organization_instance)
        # trip_templates.delete()

        # deletion of form builder app models associated with organization
        field_report_submissions = FieldReportFormSubmissions.objects.filter(
            organization=organization_instance
        )

        field_report_org_name = field_report_submissions.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete field report submission and associated models under organization :{field_report_org_name}"))
        field_report_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if field_report_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()

        for submission in field_report_submissions:
            # Delete associated FieldReportFile files from the system
            field_report_files = FieldReportFile.objects.filter(
                field_report_form_submission=submission
            )

            for file_entry in field_report_files:
                if file_entry.file:
                    if os.path.exists(file_entry.file.path):
                        os.remove(file_entry.file.path)
                file_entry.delete()

            submission.delete()

        # deleting field_report_form_config
        field_report_form_config = FieldReportFormConfig.objects.filter(
            organization=organization_instance
        )

        field_report_form_config_org_name = field_report_form_config.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete field report form config and associated models under organization :{field_report_form_config_org_name}"))
        field_report_form_config_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if field_report_form_config_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()

        field_report_form_config.delete()

        # deleting create_trip_form_submissions
        create_trip_form_submissions = CreateTripFormSubmissions.objects.filter(
            organization=organization_instance
        )
        create_trip_form_submissions_org_name = create_trip_form_submissions.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete create trip form submissions and associated models under organization :{create_trip_form_submissions_org_name}"))
        create_trip_form_submissions_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if create_trip_form_submissions_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()

        create_trip_form_submissions.delete()

        # deleting create_trip_form_config
        create_trip_form_config = CreateTripFormConfig.objects.filter(
            organization=organization_instance
        )

        create_trip_form_config_org_name = create_trip_form_config.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete create trip form config and associated models under organization :{create_trip_form_config_org_name}"))
        create_trip_form_config_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if create_trip_form_config_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()
        create_trip_form_config.delete()

        # deleting admin_report_form_submissions
        admin_report_form_submissions = AdminReportFormSubmissions.objects.filter(
            organization=organization_instance
        )

        admin_report_form_submissions_org_name = admin_report_form_submissions.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete admin report form submissions and associated models under organization :{admin_report_form_submissions_org_name}"))
        admin_report_form_submissions_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if admin_report_form_submissions_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()

        admin_report_form_submissions.delete()

        # deleting admin_report_form_config
        admin_report_form_config = AdminReportFormConfig.objects.filter(
            organization=organization_instance
        )

        admin_report_form_config_org_name = admin_report_form_config.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete  admin report form config and associated models under organization :{ admin_report_form_config_org_name}"))
        admin_report_form_config_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  admin_report_form_config_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()
        admin_report_form_config.delete()

        # deleting all trips associated with organization
        trips.delete()

        # deleting member and its associated data
        member_instance = Member.objects.filter(organization=organization_instance)

        member_instance_org_name = member_instance.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete member's model and associated models under organization :{ member_instance_org_name}"))
        member_instance_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  member_instance_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()

        for member in member_instance:
            profile = None
            member_image = None

            # deleting profile image and instance
            try:
                profile = Profile.objects.get(member=member, member__organization=organization_instance)
            except Profile.DoesNotExist:
                pass
            if profile:
                if profile.photo and os.path.exists(profile.photo.path):
                    os.remove(profile.photo.path)
                profile.delete()

            # deleting member image and instance
            try:
                member_image = MemberImage.objects.filter(member=member, member__organization=organization_instance)
            except MemberImage.DoesNotExist:
                pass
            if member_image:
                for image_i in member_image:
                    if image_i.image and os.path.exists(image_i.image.path):
                        os.remove(image_i.image.path)
                    image_i.delete()

            # deleting member
            user = member.user
            # try:
            #     user_instance = User.objects.get(email=user.email)
            # except User.DoesNotExist:
            #     pass

            member.delete()
            user.delete()

        # deleting organization and associated datas

        ride_expense_cost_matrix = RideExpenseCostMatrix.objects.filter(
            organization=organization_instance
        )

        ride_expense_cost_matrix_org_name = ride_expense_cost_matrix.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete ride expense cost matrix and associated models under organization :{ ride_expense_cost_matrix_org_name}"))
        ride_expense_cost_matrix_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  ride_expense_cost_matrix_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        ride_expense_cost_matrix.delete()


        
        vehicle= Vehicle.objects.filter(organization=organization_instance)


        vehicle_org_name = vehicle.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete vehicle model and associated models under organization :{ vehicle_org_name}"))
        vehicle_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  vehicle_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()

        fuel = Fuel.objects.filter(organization=organization_instance)

        fuel_org_name = fuel.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete fuel model and associated models under organization :{ fuel_org_name}"))
        fuel_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  fuel_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            sys.exit()
        fuel.delete()

        location = Location.objects.filter(organization=organization_instance)


        location_org_name = location.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete location model and associated models under organization :{ location_org_name}"))
        location_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  location_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        location.delete()


        organization_location =OrganizationLocation.objects.filter(organization=organization_instance)

        organization_location_org_name = organization_location.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete organization location model and associated models under organization :{organization_location_org_name}"))
        organization_location_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  organization_location_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        organization_location.delete()


        department=Department.objects.filter(organization=organization_instance)

        department_org_name = department.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete department model and associated models under organization :{ department_org_name}"))
        department_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  department_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        department.delete()


        designation=Designation.objects.filter(organization=organization_instance)


        designation_org_name = designation.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete designation model and associated models under organization :{ designation_org_name}"))
        designation_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  designation_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        designation.delete()


        external_connection =ExternalConnection.objects.filter(organization=organization_instance)


        external_connection_org_name = external_connection.order_by("organization__name").values("organization__name").distinct()
        sys.stdout.write(style_warning(f"you are about to delete external connection model and associated models under organization :{ external_connection_org_name}"))
        external_connection_confirmation = input(
            ">>> To confirm the deletion and proceed, enter 'yes'. Enter any other key to abort:  "
        )
        print("\n")
        if  external_connection_confirmation.lower() != "yes":
            sys.stdout.write(style_error("Deletion aborted."))
            exit()
        external_connection.delete()

        organization_instance.delete()

        sys.stdout.write(style_success("Organization and associated data successfully deleted."))

    except Exception as e:
        sys.stdout.write(style_error(f"ERROR: {e}."))


if __name__ == "__main__":

    delete_organization()
