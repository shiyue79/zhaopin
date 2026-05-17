from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Industry


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'level']
    list_filter = ['parent', 'level']
    search_fields = ['code', 'name']
    ordering = ['code']

    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'name', 'parent')
        }),
    )