from django.contrib import admin
from trip.models import Trip, TripDetails, TripEstimation, TripScan, TripTemplate

admin.site.register(Trip)
admin.site.register(TripDetails)
admin.site.register(TripEstimation)
admin.site.register(TripScan)
admin.site.register(TripTemplate)
