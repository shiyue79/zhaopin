# myApp/api_views/__init__.py
from .auth_views import UserViewSet
from .job_views import JobViewSet
from .employer_views import EmployerViewSet
from .application_views import ApplicationViewSet
from .talent_views import TalentViewSet
from .industry_views import IndustryViewSet
from .message_views import MessageViewSet

__all__ = [
    'UserViewSet',
    'JobViewSet',
    'EmployerViewSet',
    'ApplicationViewSet',
    'TalentViewSet',
    'IndustryViewSet',
    'MessageViewSet'
]
