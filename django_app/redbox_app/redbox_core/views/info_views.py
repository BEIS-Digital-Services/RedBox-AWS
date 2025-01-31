"""
Views for info pages like privacy notice, accessibility statement, etc.
These shouldn't contain sensitive data and don't require login.
"""

import waffle
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def privacy_notice_view(request):
    return render(
        request,
        "privacy-notice.html",
        {
            "contact_teams_general": settings.TEAMS_SUPPORT_GENERAL,
            "contact_teams_support": settings.TEAMS_SUPPORT_TECHNICAL,
            "waffle_flag": waffle.flag_is_active,
        },
    )


@require_http_methods(["GET"])
def support_view(request):
    return render(
        request, "support.html", {"contact_email": settings.CONTACT_EMAIL, "version": settings.REDBOX_VERSION, "contact_teams_general": settings.TEAMS_SUPPORT_GENERAL, "contact_teams_support": settings.TEAMS_SUPPORT_TECHNICAL}
    )


@require_http_methods(["GET"])
def accessibility_statement_view(request):
    return render(
        request,
        "accessibility-statement.html",
        {
            "contact_email": settings.CONTACT_EMAIL,
            "contact_teams_general": settings.TEAMS_SUPPORT_GENERAL,
            "contact_teams_support": settings.TEAMS_SUPPORT_TECHNICAL,
            "waffle_flag": waffle.flag_is_active,
        },
    )
