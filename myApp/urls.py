# myapp/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import UserViewSet, JobViewSet, IndustryViewSet, EmployerViewSet, TalentViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'industry', IndustryViewSet, basename='industry')
router.register(r'employer', EmployerViewSet, basename='employer')
router.register(r'talents', TalentViewSet, basename='talent')
# router.register(r'applications', ApplicationViewSet, basename='application')

urlpatterns = [
    path('', include(router.urls)),
    # 保留原有的模板视图（可选）
    # path('', TemplateView.as_view(template_name='index.html'), name='home'),
]

# 在主项目的urls.py中包含
# from django.urls import include, path
# urlpatterns = [path('', include('myapp.urls'))]
