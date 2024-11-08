from redbox_app.redbox_core.dash_apps import report_app
from redbox_app.redbox_core.views.auth_views import (oidc_callback, oidc_logout_view, sign_in_view)
from redbox_app.redbox_core.views.chat_views import ChatsTitleView, ChatsView, DeleteChat, UpdateChatFeedback
from redbox_app.redbox_core.views.citation_views import CitationsView
from redbox_app.redbox_core.views.demographics_views import (
    CheckDemographicsView,
    DemographicsView,
    UpdateDemographicsView,
)

from redbox_app.redbox_core.views.custom_oidc_views import \
    CustomOIDCAuthenticationRequestView

from redbox_app.redbox_core.views.document_views import (
    DocumentView,
    UploadView,
    file_status_api_view,
    remove_doc_view,
)
from redbox_app.redbox_core.views.info_views import accessibility_statement_view, privacy_notice_view, support_view
from redbox_app.redbox_core.views.misc_views import SecurityTxtRedirectView, health, homepage_view
from redbox_app.redbox_core.views.ratings_views import RatingsView
from redbox_app.redbox_core.views.signup_views import Signup1, Signup2, Signup3, Signup4, Signup5, Signup6, Signup7

__all__ = [
    "ChatsTitleView",
    "ChatsView",
    "CitationsView",
    "CheckDemographicsView",
    "DemographicsView",
    "DocumentView",
    "RatingsView",
    "SecurityTxtRedirectView",
    "UploadView",
    "UpdateDemographicsView",
    "file_status_api_view",
    "health",
    "homepage_view",
    "remove_doc_view",
    "privacy_notice_view",
    "accessibility_statement_view",
    "support_view",
    "Signup1",
    "Signup2",
    "Signup3",
    "Signup4",
    "Signup5",
    "Signup6",
    "Signup7",
    "report_app",
    "UpdateChatFeedback",
    "DeleteChat",
    "CustomOIDCAuthenticationRequestView",
    "oidc_callback",
    "oidc_logout_view",
    "sign_in_view"
]
