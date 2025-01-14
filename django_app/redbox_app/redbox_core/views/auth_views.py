import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponseServerError
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from magic_link.models import MagicLink
from requests import HTTPError
from urllib.parse import urlencode

from redbox_app.redbox_core.forms import SignInForm

logger = logging.getLogger(__name__)
User = get_user_model()

def oidc_callback(request):
    # Get the code and state from the query parameters
    code = request.GET.get('code')
    state = request.GET.get('state')

    # Retrieve the original state from the session to prevent CSRF
    stored_state = request.session.get('oidc_state')
    
    # Check for state mismatch or missing code
    if not code or not state or state != stored_state:
        logger.error("Invalid callback parameters or state mismatch")
        return HttpResponseServerError(f"Invalid callback parameters or state mismatch.")

    # Retrieve code_verifier from the session for PKCE
    code_verifier = request.session.get('code_verifier')
    if not code_verifier:
        logger.error("PKCE code_verifier is missing")
        return HttpResponseServerError("PKCE code_verifier is missing")

    # Authenticate the user and handle the token exchange
    user = authenticate(request=request, code=code, state=state, code_verifier=code_verifier)
    
    # If user authentication is successful, log in the user
    if user is not None and user.is_active:
        login(request, user)
        return redirect('/')  # Redirect to the home page or desired location
    else:
        logger.error("Authentication failed or user is inactive")
        return HttpResponseServerError("Authentication failed or user is inactive")
    
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

def oidc_logout_view(request):
    """
    Log out the user locally and redirect to Okta's logout endpoint.
    """
    # Retrieve the id_token from the session
    id_token = request.session.get('id_token')
    if not id_token:
        logger.warning("No id_token found in session during logout.")
    
    # Log out the user locally
    logout(request)

    # Clear the id_token from the session
    if 'id_token' in request.session:
        del request.session['id_token']
        logger.debug("Cleared id_token from session after logout.")

    # Construct the logout URL
    params = {
        'post_logout_redirect_uri': settings.LOGOUT_REDIRECT_URL
    }

    if id_token:
        params['id_token_hint'] = id_token

    query = urlencode(params)
    logout_url = f"{settings.OIDC_OP_ISSUER}/v1/logout?{query}"
    
    logger.debug(f"Redirecting to Okta logout URL: {logout_url}")
    
    return redirect(logout_url)

def sign_in_view(request: HttpRequest):
    return redirect("/oidc/authenticate/")
#    if request.user.is_authenticated:
#        return redirect("homepage")
#    if settings.LOGIN_METHOD == "sso":
#        return redirect("/auth/login/")
#    if request.method == "POST":
#        form = SignInForm(request.POST)
#        if form.is_valid():
#            email = form.cleaned_data["email"].lower()
#
#            try:
#                user = User.objects.get(email=email)
#                link = MagicLink.objects.create(
#                    user=user, redirect_to="/check-demographics"
#                )  # Switch this to "/chats" once profile overlay is added to Chats page
#                full_link = request.build_absolute_uri(link.get_absolute_url())
#                body = render_to_string("email/verification.txt", {"url": full_link})
#                send_mail(
#                    subject="Redbox sign-in",
#                    message=body,
#                    from_email=settings.FROM_EMAIL,
#                    recipient_list=[email],
#                )
#            except User.DoesNotExist as e:
#                logger.debug("User with email %s not found", email, exc_info=e)
#            except HTTPError as e:
#                logger.exception("failed to send link to %s", email, exc_info=e)
#
#            return redirect("sign-in-link-sent")
#
#        return render(
#            request,
#            template_name="sign-in.html",
#            context={
#                "errors": form.errors,
#            },
#        )
#
#    return render(
#        request,
#        template_name="sign-in.html",
#        context={"request": request},
#    )


#def sign_in_link_sent_view(request: HttpRequest):
#    if request.user.is_authenticated:
#        return redirect("homepage")
#    return render(
#        request,
#        template_name="sign-in-link-sent.html",
#        context={"request": request},
#    )
#
#
#def signed_out_view(request: HttpRequest):
#    logout(request)
#    return redirect("homepage")
