# redbox_app/oidc_auth.py

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from jwt import PyJWKClient
import jwt
import logging
from django.http import HttpRequest, HttpResponseServerError

User = get_user_model()
logger = logging.getLogger(__name__)

class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):

    def exchange_code_for_token(self, code, code_verifier):
        """
        Exchange the authorization code for tokens.
        """
        token_params = {
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': settings.OIDC_RP_CALLBACK_URL,
            'code_verifier': code_verifier,
            'client_id': settings.OIDC_RP_CLIENT_ID,
            'client_secret': settings.OIDC_RP_CLIENT_SECRET,
        }

        try:
            token_response = requests.post(
                settings.OIDC_OP_TOKEN_ENDPOINT,
                data=token_params,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            token_response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Token exchange failed: {e}")
            return None

        return token_response.json()

    def get_claims_from_id_token(self, id_token):
        """
        Decode and validate the ID token to extract claims.
        """
        try:
            jwks_client = PyJWKClient(settings.OIDC_OP_JWKS_ENDPOINT)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token).key

            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=settings.OIDC_RP_CLIENT_ID,
                issuer=settings.OIDC_OP_ISSUER,
                options={"verify_exp": True}
            )
            return claims
        except jwt.PyJWTError as e:
            logger.error(f"Failed to decode ID token: {e}")
            return None

    def create_user(self, claims):
        email = claims.get('email')
        if not email:
            logger.error("No email claim found in ID token.")
            return None

        user, created = User.objects.get_or_create(email=email)
        if not created:
            # If user exists, return existing user
            return user

        # Set other fields based on the claims
        user.name = claims.get('name', '')
        user.verified = True  # Assuming OIDC authenticated users are verified
        user.is_active = True  # Ensure user is active

        if 'is_redbox_admin' in claims:
            user.is_staff = True
            user.is_superuser = True

        # Save the user
        user.save()
        return user

    def update_user(self, user, claims):
        user.name = claims.get('name', user.name)
        user.verified = True
        user.is_active = True  # Ensure user is active

        if 'is_redbox_admin' in claims:
            user.is_staff = True
            user.is_superuser = True

        # Save the updated user
        user.save()
        return user

    def filter_users_by_claims(self, claims):
        email = claims.get('email')
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)
    
    def authenticate(self, request, code, state, code_verifier):
        """
        Authenticate the user using the authorization code and code_verifier.
        """
        if not code or not state or not code_verifier:
            logger.error("Missing code, state, or code_verifier.")
            return None  # Fail gracefully if they aren't provided

        # Exchange the authorization code for tokens
        token_data = self.exchange_code_for_token(code, code_verifier)

        if not token_data or 'id_token' not in token_data:
            logger.error("No id_token found in token response.")
            return None  # If no tokens are returned, fail authentication

        id_token = token_data['id_token']
        request.session['id_token'] = id_token

        claims = self.get_claims_from_id_token(id_token)

        if not claims:
            logger.error("Failed to extract claims from id_token.")
            return None

        # Find or create the user based on the claims
        users = self.filter_users_by_claims(claims)
        if users.exists():
            user = self.update_user(users.first(), claims)
        else:
            user = self.create_user(claims)

        return user
