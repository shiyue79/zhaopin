# myApp/api_views/talent_views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import models
from ..models import User
from ..serializers import TalentSerializer

class TalentViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='list')
    def talent_list(self, request):
        try:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('size', 10))
            keyword = request.GET.get('keyword', '')
            city = request.GET.get('location', '')
            education = request.GET.get('education', '')
            experience = request.GET.get('experience', '')
            queryset = User.objects.all()

            if keyword:
                queryset = queryset.filter(
                    models.Q(realName__icontains=keyword) |
                    models.Q(username__icontains=keyword) |
                    models.Q(work__icontains=keyword)
                )
            if city:
                queryset = queryset.filter(city__icontains=city)
            if education:
                queryset = queryset.filter(edu=education)
            if experience:
                queryset = queryset.filter(exp=experience)
            queryset = queryset.order_by('-lastLoginTime', '-createTime')
            paginator = Paginator(queryset, page_size)
            if page < 1:
                page = 1
            elif page > paginator.num_pages:
                page = paginator.num_pages
            current_page = paginator.page(page)
            serializer = TalentSerializer(current_page.object_list, many=True)
            talent_list = []
            for item in serializer.data:
                talent_data = {
                    'id': item['id'],
                    'username': item['username'],
                    'realName': item['realName'],
                    'sex': item['sex'],
                    'age': item['age'],
                    'mobile': item['mobile'],
                    'email': item['email'],
                    'education': item['edu'],
                    'experience': item['exp'],
                    'city': item['city'],
                    'work': item['work'],
                    'avatar': request.build_absolute_uri(item['avatar']) if item['avatar'] else None,
                    'resume': request.build_absolute_uri(item['resume']) if item['resume'] else None,
                    'lastLoginTime': item['lastLoginTime'],
                    'isOnline': item['isOnline']
                }
                talent_list.append(talent_data)

            return JsonResponse({
                'code': 200,
                'msg': '获取人才列表成功',
                'data': {
                    'talents': talent_list,
                    'pagination': {
                        'current': page,
                        'pageSize': page_size,
                        'total': paginator.count,
                        'totalPages': paginator.num_pages
                    }
                }
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取人才列表失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'获取人才列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'])
    def recommended(self, request):
        """获取推荐人才列表"""
        try:
            # 这里可以实现智能推荐算法
            # 暂时返回最近活跃的人才作为推荐
            talents = User.objects.filter(isOnline=True).order_by('-lastLoginTime')[:10]

            serializer = TalentSerializer(talents, many=True)
            talent_list = []
            for item in serializer.data:
                talent_data = {
                    'id': item['id'],
                    'username': item['username'],
                    'realName': item['realName'],
                    'sex': item['sex'],
                    'age': item['age'],
                    'mobile': item['mobile'],
                    'email': item['email'],
                    'education': item['edu'],
                    'experience': item['exp'],
                    'city': item['city'],
                    'work': item['work'],
                    'avatar': request.build_absolute_uri(item['avatar']) if item['avatar'] else None,
                    'resume': request.build_absolute_uri(item['resume']) if item['resume'] else None,
                    'lastLoginTime': item['lastLoginTime'],
                    'isOnline': item['isOnline']
                }
                talent_list.append(talent_data)

            return JsonResponse({
                'code': 200,
                'msg': '获取推荐人才列表成功',
                'data': talent_list
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取推荐人才列表失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'获取推荐人才列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'])
    def analysis(self, request):
        """获取候选人匹配分析"""
        try:
            candidate_id = request.GET.get('id')
            if not candidate_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少候选人ID参数',
                    'data': None
                }, status=400)

            try:
                candidate = User.objects.get(id=candidate_id)
            except User.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'msg': '候选人不存在',
                    'data': None
                }, status=404)

            # 这里可以实现智能匹配分析算法
            # 暂时返回固定的分析结果
            analysis_data = {
                'candidateId': candidate.id,
                'candidateName': candidate.realName or candidate.username,
                'matchScore': 85.5,
                'strengths': [
                    '工作经验丰富',
                    '技能匹配度高',
                    '学历背景良好'
                ],
                'weaknesses': [
                    '行业经验略有不足',
                    '地域匹配度一般'
                ],
                'suggestions': [
                    '建议进一步沟通了解职业规划',
                    '可以安排技术面试验证专业能力',
                    '考虑提供培训机会弥补行业知识差距'
                ]
            }

            return JsonResponse({
                'code': 200,
                'msg': '获取匹配分析成功',
                'data': analysis_data
            }, status=200)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取匹配分析失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'获取匹配分析失败: {str(e)}',
                'data': None
            }, status=500)
