from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as Base
from .models import User

@admin.register(User)
class UserAdmin(Base):
    list_display  = ['email', 'full_name', 'role', 'department', 'is_active']
    list_filter   = ['role', 'is_active']
    search_fields = ['email', 'full_name']
    ordering      = ['full_name']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Info', {'fields': ('full_name', 'department', 'phone')}),
        ('Access', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'full_name', 'role', 'password1', 'password2')}),)
