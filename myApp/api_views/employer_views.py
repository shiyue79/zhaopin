# myApp/api_views/employer_views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django.http import JsonResponse
from ..utils import getCompanyInfo

class EmployerViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def enterpriseInfo(self, request):
        username = request.session.get('username')
        account = request.session.get('account')

        if not username or not account:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        if account != 'admin':
            return JsonResponse({
                'code': 403,
                'msg': '权限不足，仅企业管理员可访问',
                'data': None
            }, status=403)

        try:
            company_data = getCompanyInfo.getCompanyInfo(username)

            if not company_data:
                return JsonResponse({
                    'code': 404,
                    'msg': '企业信息不存在',
                    'data': None
                }, status=404)

            return JsonResponse({
                'code': 200,
                'msg': '获取企业信息成功',
                'data': company_data
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取企业信息失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取企业信息失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'])
    def saveEnterpriseInfo(self, request):
        username = request.session.get('username')
        account = request.session.get('account')

        if not username or not account:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        if account != 'admin':
            return JsonResponse({
                'code': 403,
                'msg': '权限不足，仅企业管理员可访问',
                'data': None
            }, status=403)

        try:
            data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
            files = request.FILES if request.FILES else None

            result = getCompanyInfo.saveCompanyInfo(username, data, files)

            if result['success']:
                return JsonResponse({
                    'code': 200,
                    'msg': result['message'],
                    'data': None
                }, status=200)
            else:
                return JsonResponse({
                    'code': 400,
                    'msg': result['message'],
                    'data': None
                }, status=400)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"保存企业信息失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '保存失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'])
    def submitCertification(self, request):
        username = request.session.get('username')
        account = request.session.get('account')
        if not username or not account:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        if account != 'admin':
            return JsonResponse({
                'code': 403,
                'msg': '权限不足，仅企业管理员可访问',
                'data': None
            }, status=403)

        try:
            files = request.FILES if request.FILES else None

            result = getCompanyInfo.submitCertification(username, files)

            if result['success']:
                return JsonResponse({
                    'code': 200,
                    'msg': result['message'],
                    'data': None
                }, status=200)
            else:
                return JsonResponse({
                    'code': 400,
                    'msg': result['message'],
                    'data': None
                }, status=400)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"提交认证失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '提交认证失败，请稍后重试',
                'data': None
            }, status=500)
