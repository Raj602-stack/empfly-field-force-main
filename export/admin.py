from django.contrib import admin

# Register your models here.
from export.models import ExportRequest

admin.site.register(ExportRequest)
