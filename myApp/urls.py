# myApp/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    UserViewSet,
    JobViewSet,
    EmployerViewSet,
    ApplicationViewSet,
    TalentViewSet,
    IndustryViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'employer', EmployerViewSet, basename='employer')
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'talents', TalentViewSet, basename='talent')
router.register(r'industry', IndustryViewSet, basename='industry')

urlpatterns = [
    path('', include(router.urls)),
]

# 在主项目的urls.py中包含
# from django.urls import include, path
# urlpatterns = [path('', include('myapp.urls'))]
