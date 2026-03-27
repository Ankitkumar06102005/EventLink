from django.contrib import admin
from .models import Profile, Virtue, Team, Event, EventRegistration, Stage, TeamProgress


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'role', 'class_name']
    list_filter = ['role']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'date', 'location']


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['team', 'event', 'status', 'submitted_at']
    list_filter = ['status']
    list_editable = ['status']


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'order']
    list_filter = ['event']


@admin.register(TeamProgress)
class TeamProgressAdmin(admin.ModelAdmin):
    list_display = ['team', 'stage', 'status', 'updated_at']
    list_filter = ['status']
    list_editable = ['status']


admin.site.register(Virtue)
admin.site.register(Team)
