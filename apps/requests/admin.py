from django.contrib import admin
from .models import VenueRequest

@admin.register(VenueRequest)
class VenueRequestAdmin(admin.ModelAdmin):
    list_display  = ['venue', 'requested_by', 'date', 'start_time', 'end_time', 'status']
    list_filter   = ['status', 'date']
    search_fields = ['purpose', 'requested_by__full_name']
