import json

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import sync_and_async_middleware
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect

class EnforceConsentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if user is authenticated and has not completed consent
        if request.user.is_authenticated and request.user.is_staff == False and request.user.is_superuser == False:
            # List of required consents
            required_consents = [
                "consent_research",
                "consent_interviews",
                "consent_feedback",
                "consent_confidentiality",
                "consent_understand",
                "consent_agreement",
            ]
            # If any consent is False, redirect to the first page
            if not all(getattr(request.user, consent, False) for consent in required_consents):
                if not request.path.startswith(reverse("sign-up-page-1")):
                    return redirect("sign-up-page-1")
        return self.get_response(request)
    
@sync_and_async_middleware
def nocache_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request: HttpRequest) -> HttpResponse:
            response = await get_response(request)
            response["Cache-Control"] = "no-store"
            return response
    else:

        def middleware(request: HttpRequest) -> HttpResponse:
            response = get_response(request)
            response["Cache-Control"] = "no-store"
            return response

    return middleware


@sync_and_async_middleware
def security_header_middleware(get_response):
    report_to = json.dumps(
        {
            "group": "csp-endpoint",
            "max_age": 10886400,
            "endpoints": [{"url": settings.SENTRY_REPORT_TO_ENDPOINT}],
            "include_subdomains": True,
        },
        indent=None,
        separators=(",", ":"),
        default=str,
    )

    if iscoroutinefunction(get_response):

        async def middleware(request: HttpRequest) -> HttpResponse:
            response = await get_response(request)
            if settings.SENTRY_REPORT_TO_ENDPOINT:
                response["Report-To"] = report_to
            return response
    else:

        def middleware(request: HttpRequest) -> HttpResponse:
            response = get_response(request)
            if settings.SENTRY_REPORT_TO_ENDPOINT:
                response["Report-To"] = report_to
            return response

    return middleware


@sync_and_async_middleware
def plotly_no_csp_no_xframe_middleware(get_response):
    if iscoroutinefunction(get_response):

        async def middleware(request: HttpRequest) -> HttpResponse:
            response = await get_response(request)
            if "admin/report" in request.path:
                response.headers.pop("Content-Security-Policy", None)
                response.headers.pop("X-Frame-Options", None)
            return response
    else:

        def middleware(request: HttpRequest) -> HttpResponse:
            response = get_response(request)
            if "admin/report" in request.path:
                response.headers.pop("Content-Security-Policy", None)
                response.headers.pop("X-Frame-Options", None)
            return response

    return middleware
