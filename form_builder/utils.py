from .models import AdminReportFormConfig
def get_admin_report_config_field(department_uuid, org_uuid):

    try:
        return AdminReportFormConfig.objects.get(department__uuid=department_uuid,organization__uuid=org_uuid)
    except AdminReportFormConfig.DoesNotExist:
        return