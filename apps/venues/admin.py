from django.contrib import admin
from .models import Building, Venue

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'location']
    search_fields = ['name', 'code']

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'building', 'venue_type', 'capacity', 'is_active']
    list_filter   = ['venue_type', 'is_active', 'building']
    search_fields = ['code', 'name']
