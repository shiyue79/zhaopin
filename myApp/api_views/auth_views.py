from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from ..models import User, Employer,Company
from ..serializers import UserSerializer
import hashlib
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from ..utils import getSelfInfo, getChangePwd
from django.db import models

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register_admin(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        company_name = request.data.get('companyName')
        company_id = request.data.get('companyId')
        if not all([username, password]):
            return JsonResponse({
                'code': 400,
                'msg': '用户名和密码不能为空',
                'data': None
            }, status=400)
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return JsonResponse({
                    'code': 400,
                    'msg': '公司不存在',
                    'data': None
                }, status=400)
        else:
            return JsonResponse({
                'code': 400,
                'msg': '请提供 companyId 或 companyName',
                'data': None
            }, status=400)
        try:
            if Employer.objects.filter(username=username).exists():
                return JsonResponse({
                    'code': 400,
                    'msg': '用户名已存在',
                    'data': None
                }, status=400)
            md5 = hashlib.md5()
            md5.update(password.encode())
            pwd = md5.hexdigest()
            employer = Employer.objects.create(
                username=username,
                password=pwd,
                comName=company.name,
                company=company,
            )
            return JsonResponse({
                'code': 200,
                'msg': '注册成功',
                'data': {
                    'userId': employer.id,
                    'username': employer.username,
                    'companyName': employer.comName,
                    'companyId': company.id,
                }
            }, status=201)
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': '注册失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register_user(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not all([username, password]):
            return JsonResponse({
                'code': 400,
                'msg': '用户名和密码不能为空',
                'data': None
            }, status=400)

        try:
            if User.objects.filter(username=username).exists():
                return JsonResponse({
                    'code': 400,
                    'msg': '用户名已存在',
                    'data': None
                }, status=400)
            md5 = hashlib.md5()
            md5.update(password.encode())
            pwd = md5.hexdigest()
            user = User.objects.create(
                username=username,
                password=pwd
            )
            return JsonResponse({
                'code': 200,
                'msg': '注册成功',
                'data': {
                    'userId': user.id,
                    'username': user.username,
                }
            }, status=201)
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': '注册失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def create_company(self, request):
        username = request.session.get('username')
        account = request.session.get('account')
        name = request.data.get('name')
        industry = request.data.get('industry', '')
        scale = request.data.get('scale', '')
        if not name:
            return JsonResponse({
                'code': 400,
                'msg': '公司名称不能为空',
                'data': None
            }, status=400)
        try:
            # 检查公司名称是否已存在
            existing_company = Company.objects.filter(name=name).first()
            if existing_company :
                return JsonResponse({
                    'code': 400,
                    'msg': '公司名称已被认证，请使用其他名称',
                    'data': None
                }, status=400)
            # 创建公司
            company = Company.objects.create(
                name=name,
                size=scale,
                tag=industry,
            )
            return JsonResponse({
                'code': 200,
                'msg': '公司创建成功',
                'data': {
                    'id': company.id,
                    'name': company.name,
                    'size': company.size,
                    'tag': company.tag,
                    'location': company.location
                }
            }, status=201)
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': '创建失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def search_company(self, request):
        keyword = request.GET.get('keyword', '').strip()
        if not keyword:
            return JsonResponse({
                'code': 400,
                'msg': '搜索关键词不能为空',
                'data': []
            }, status=400)
        try:
            companies = Company.objects.filter(
                models.Q(name__icontains=keyword)
            ).values(
                'id', 'name'
            )[:50]  # 限制返回结果数量
            company_list = list(companies)
            return JsonResponse({
                'code': 200,
                'msg': '搜索成功',
                'data': company_list
            }, status=200)
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': '搜索失败',
                'data': []
            }, status=500)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        md5 = hashlib.md5()
        md5.update(password.encode())
        pwd = md5.hexdigest()
        account = request.data.get('account')
        try:
            if account == 'user':
                user = User.objects.get(username=username, password=pwd)
                user.lastLoginTime = timezone.now()
                user.isOnline = True
                user.save()
            elif account == 'admin':
                user = Employer.objects.get(username=username, password=pwd)
                user.lastLoginTime = timezone.now()
                user.isOnline = True
                user.save()
            else:
                return Response({'error': 'Invalid account'}, status=status.HTTP_400_BAD_REQUEST)
            request.session['username'] = user.username
            request.session['account'] = account
            refresh = RefreshToken.for_user(user)
            return JsonResponse({
                'code': 200,
                'msg': '登录成功',
                'data': {
                    'token': str(refresh.access_token),
                    'refreshToken': str(refresh)
                }
            })
        except (User.DoesNotExist, Employer.DoesNotExist):
            return JsonResponse({
                'code': 401,
                'msg': '用户名或密码不正确',
                'data': None
            }, status=401)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Login failed for user {username}: {e}")
            return JsonResponse({
                'code': 401,
                'msg': '登录失败，请稍后重试',
                'data': None
            }, status=401)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def logout(self, request):
        logout(request)
        username = request.session.get('username')
        account = request.data.get('account')
        try:
            if account == 'user':
                user = User.objects.get(username=username)
            else:
                user = Employer.objects.get(username=username)
            user.lastLoginTime = timezone.now()
            user.isOnline = False
            user.save()
        except:
            return JsonResponse({
                'code': 401,
                'msg': '用户不存在',
                'data': None
            }, status=401)
        return Response({'message': 'Logged out'})

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def info(self, request):
        username = request.session.get('username')
        account = request.session.get('account')
        # 检查是否已登录
        if not username or not account:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)
        try:
            if account == 'user':
                user = User.objects.get(username=username)
                user_data = {
                    'userId': user.id,
                    'username': user.username,
                    'roles': 'R_USER',
                    'realName': user.realName,
                    'sex': user.sex,
                    'age': user.age,
                    'mobile': user.mobile,
                    'email': user.email,
                    'education': user.edu,
                    'experience': user.exp,
                    'city': user.city,
                    'work': user.work,
                    'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
                    'resume': request.build_absolute_uri(user.resume.url) if user.resume else None
                }
            elif account == 'admin':
                user = Employer.objects.get(username=username)
                user_data = {
                    'userId': user.id,
                    'username': user.username,
                    'roles': 'R_ADMIN',
                    'realName': user.realName,
                    'sex': user.sex,
                    'position': user.position,
                    'company': user.company.id,
                    'comName': user.comName,
                    'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None
                }
            else:
                return JsonResponse({
                    'code': 400,
                    'msg': '无效的账户类型',
                    'data': None
                }, status=400)

            return JsonResponse({
                'code': 200,
                'msg': '获取用户信息成功',
                'data': user_data
            }, status=200)

        except (User.DoesNotExist, Employer.DoesNotExist):
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get user info for {username}: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '服务器内部错误',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'], permission_classes=[permissions.AllowAny])
    def updateInfo(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            from django.http import QueryDict
            post_data = QueryDict('', mutable=True)
            for key, value in request.data.items():
                if key != 'resume' and key != 'avatar':
                    post_data[key] = value
            post_data['username'] = username
            files_data = request.FILES
            getSelfInfo.changeSelfInfo(post_data, files_data)
            user = User.objects.get(username=username)
            return JsonResponse({
                'code': 200,
                'msg': '个人信息更新成功',
                'data': {
                    'userId': user.id,
                    'username': user.username,
                    'realName': user.realName,
                    'sex': user.sex,
                    'age': user.age,
                    'mobile': user.mobile,
                    'email': user.email,
                    'edu': user.edu,
                    'exp': user.exp,
                    'city': user.city,
                    'work': user.work
                }
            }, status=200)

        except User.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新用户信息失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '更新失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def changePassword(self, request):
        username = request.session.get('username')
        account = request.session.get('account')
        if not username or not account:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)
        try:
            password_data = {
                'oldPwd': request.data.get('oldPwd'),
                'newPwd': request.data.get('newPwd'),
                'checkPwd': request.data.get('checkPwd')
            }
            error_msg = getChangePwd.checkPwd(username, account, password_data)
            if error_msg:
                return JsonResponse({
                    'code': 400,
                    'msg': error_msg,
                    'data': None
                }, status=400)

            return JsonResponse({
                'code': 200,
                'msg': '密码修改成功',
                'data': None
            }, status=200)

        except (User.DoesNotExist, Employer.DoesNotExist):
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"修改密码失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '修改失败，请稍后重试',
                'data': None
            }, status=500)

