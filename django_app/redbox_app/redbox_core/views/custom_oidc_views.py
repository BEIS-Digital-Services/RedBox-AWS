# redbox_app/redbox_core/views/auth_views.py

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from django.conf import settings  # Import settings
from django.shortcuts import redirect  # Import the redirect function
from django.utils.crypto import get_random_string  # Correct method
from mozilla_django_oidc.views import OIDCAuthenticationRequestView

class CustomOIDCAuthenticationRequestView(OIDCAuthenticationRequestView):
    def get(self, request):
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        request.session['code_verifier'] = code_verifier

        state = get_random_string(32)
        params = {
            'response_type': 'code',
            'scope': 'openid profile email',
            'client_id': settings.OIDC_RP_CLIENT_ID,
            'redirect_uri': settings.OIDC_RP_CALLBACK_URL,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }

        request.session['oidc_state'] = state
        request.session.save()

        query = urlencode(params)
        redirect_url = f'{settings.OIDC_OP_AUTHORIZATION_ENDPOINT}?{query}'
        return redirect(redirect_url)
