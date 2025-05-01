from django.contrib import admin
from .models import FieldReportFile, FieldReportFormSubmissions, FieldReportFormConfig, CreateTripFormConfig, CreateTripFormSubmissions, AdminReportFormConfig, AdminReportFormSubmissions

# Register your models here.

admin.site.register(FieldReportFormSubmissions)
admin.site.register(FieldReportFormConfig)
admin.site.register(FieldReportFile)
admin.site.register(CreateTripFormConfig)
admin.site.register(CreateTripFormSubmissions)
admin.site.register(AdminReportFormConfig)
admin.site.register(AdminReportFormSubmissions)
