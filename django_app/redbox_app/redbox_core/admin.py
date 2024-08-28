import csv
import logging

from django.conf import settings
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpResponse
from django_q.tasks import async_task
from import_export.admin import ExportMixin, ImportExportMixin

from redbox_app.redbox_core.client import CoreApiClient
from redbox_app.worker import ingest

from . import models

logger = logging.getLogger(__name__)
core_api = CoreApiClient(host=settings.CORE_API_HOST, port=settings.CORE_API_PORT)


class UserAdmin(ImportExportMixin, admin.ModelAdmin):
    fields = [
        "email",
        "name",
        "ai_experience",
        "business_unit",
        "grade",
        "profession",
        "is_superuser",
        "is_staff",
        "last_login",
        "ai_settings",
    ]
    list_display = [
        "email",
        "name",
        "get_ai",
        "business_unit",
        "grade",
        "profession",
        "is_superuser",
        "is_staff",
        "last_login",
    ]
    list_filter = ["business_unit", "grade", "profession"]
    date_hierarchy = "last_login"

    @admin.display(ordering="ai_experience", description="AI Experience")
    def get_ai(self, obj: models.User):
        return obj.ai_experience

    class Meta:
        model = models.User
        fields = ["email"]
        import_id_fields = ["email"]


class FileAdmin(ExportMixin, admin.ModelAdmin):
    def reupload(self, _request, queryset):
        for file in queryset:
            logger.info("Re-uploading file to core-api: %s", file)
            async_task(ingest, file.id)
            logger.info("Successfully reuploaded file %s.", file)

    list_display = ["original_file_name", "user", "status", "created_at", "last_referenced"]
    list_filter = ["user", "status"]
    date_hierarchy = "created_at"
    actions = ["reupload"]


class CitationInline(admin.StackedInline):
    model = models.Citation
    ordering = ("modified_at",)

    extra = 0


class ChatMessageTokenUseInline(admin.StackedInline):
    model = models.ChatMessageTokenUse
    ordering = ("modified_at",)

    extra = 0


class ChatMessageTokenUseAdmin(ExportMixin, admin.ModelAdmin):
    pass


class ChatMessageAdmin(ExportMixin, admin.ModelAdmin):
    list_display = ["short_text", "role", "get_user", "chat", "route", "created_at"]
    list_filter = ["role", "route", "chat__user"]
    date_hierarchy = "created_at"
    inlines = [CitationInline, ChatMessageTokenUseInline]
    readonly_fields = ["selected_files", "source_files"]

    @admin.display(ordering="chat__user", description="User")
    def get_user(self, obj):
        return obj.chat.user

    @admin.display(description="text")
    def short_text(self, obj):
        max_length = 128
        if len(obj.text) < max_length:
            return obj.text
        return obj.text[: max_length - 3] + "..."


class ChatMessageInline(admin.StackedInline):
    model = models.ChatMessage
    ordering = ("modified_at",)
    fields = ["text", "role", "route", "rating"]
    readonly_fields = ["text", "role", "route", "rating"]
    extra = 1
    show_change_link = True  # allows users to click through to look at Citations


class ChatAdmin(ExportMixin, admin.ModelAdmin):
    def export_as_csv(self, request, queryset: QuerySet):  # noqa:ARG002
        history_field_names: list[str] = [field.name for field in models.Chat._meta.fields]  # noqa:SLF001
        message_field_names: list[str] = [field.name for field in models.ChatMessage._meta.fields]  # noqa:SLF001

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=chat.csv"
        writer = csv.writer(response)

        writer.writerow(["history_" + n for n in history_field_names] + ["message_" + n for n in message_field_names])
        chat_message: models.ChatMessage
        for chat in queryset:
            for chat_message in chat.chatmessage_set.all():
                row = [getattr(chat, field) for field in history_field_names] + [
                    getattr(chat_message, field) for field in message_field_names
                ]
                writer.writerow(row)

        return response

    export_as_csv.short_description = "Export Selected"
    fields = ["name", "user"]
    inlines = [ChatMessageInline]
    list_display = ["name", "user", "created_at"]
    list_filter = ["user"]
    date_hierarchy = "created_at"
    actions = ["export_as_csv"]


admin.site.register(models.User, UserAdmin)
admin.site.register(models.File, FileAdmin)
admin.site.register(models.Chat, ChatAdmin)
admin.site.register(models.ChatMessage, ChatMessageAdmin)
admin.site.register(models.AISettings)
admin.site.register(models.ChatMessageTokenUse, ChatMessageTokenUseAdmin)
