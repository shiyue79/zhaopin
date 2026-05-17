# myApp/api_views/industry_views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from django.http import JsonResponse
from ..models import Industry
from ..serializers import IndustrySerializer

class IndustryViewSet(viewsets.ModelViewSet):
    queryset = Industry.objects.filter(parent__isnull=True)
    serializer_class = IndustrySerializer

    @action(detail=False, methods=['get'])
    def tree(self, request):
        try:
            root_industries = Industry.objects.filter(parent__isnull=True)
            serializer = self.get_serializer(root_industries, many=True)

            return JsonResponse({
                'code': 200,
                'msg': '获取行业树成功',
                'data': serializer.data
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取行业树失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取行业树失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'])
    def flat(self, request):
        try:
            all_industries = Industry.objects.all()
            data = [
                {
                    'code': industry.code,
                    'name': industry.name,
                    'parent_code': industry.parent.code if industry.parent else None
                }
                for industry in all_industries
            ]

            return JsonResponse({
                'code': 200,
                'msg': '获取行业列表成功',
                'data': data
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取行业列表失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取行业列表失败，请稍后重试',
                'data': None
            }, status=500)
