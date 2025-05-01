from django.contrib import admin
from organization.models import (
    ExternalConnection,
    Organization,
    Fuel,
    OrganizationLocation,
    Vehicle,
    RideExpenseCostMatrix,
    Location,
    Role,
    Designation,
    Department
)
from .forms import OrgAdmin

admin.site.register(Organization, OrgAdmin)
admin.site.register(Fuel)
admin.site.register(Vehicle)
admin.site.register(RideExpenseCostMatrix)
admin.site.register(Location)
admin.site.register(Role)
admin.site.register(Designation)
admin.site.register(Department)
admin.site.register(OrganizationLocation)
admin.site.register(ExternalConnection)
