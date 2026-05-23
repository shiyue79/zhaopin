# myApp/api_views/job_views.py
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django.http import JsonResponse
from django.core.cache import cache
from django.core.paginator import Paginator
from ..models import User, Joblist, Employer, Industry, History,Favorite,Application
from ..serializers import JobSerializer
import hashlib


class JobViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'])
    def joblist(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            userInfo = User.objects.get(username=username)

            # 获取筛选参数
            work = request.GET.get('work', '')
            city = request.GET.get('city', '')
            industry = request.GET.get('industry', '')
            education = request.GET.get('education', '不限')
            experience = request.GET.get('experience', '不限')
            salary_min = request.GET.get('salaryMin', '')
            company_size = request.GET.get('companySize', '')
            job_types = request.GET.get('jobTypes', '')

            # 分页参数
            current_page = int(request.GET.get('current', request.GET.get('page', 1)))
            page_size = int(request.GET.get('size', request.GET.get('pageSize', 10)))

            # 构建查询条件
            from django.db.models import Q
            filters = Q(delete=0)

            if work:
                filters &= Q(name__icontains=work) | Q(keyList__icontains=work)
            if city:
                filters &= Q(city__icontains=city)
            if industry:
                if industry.endswith('_child'):
                    parent_code = industry.replace('_child', '')
                    filters &= Q(industry__startswith=parent_code)
                else:
                    filters &= Q(industry__icontains=industry)
            if education and education != '不限':
                filters &= Q(edu=education)
            if experience and experience != '不限':
                filters &= Q(exp=experience)
            if salary_min:
                try:
                    filters &= Q(salaryMin__gte=float(salary_min))
                except ValueError:
                    pass
            if company_size:
                filters &= Q(comSize=company_size)
            if job_types:
                # 多选，用逗号分隔
                types_list = job_types.split(',')
                type_filter = Q()
                for job_type in types_list:
                    type_filter |= Q(type__icontains=job_type.strip())
                filters &= type_filter

            # 获取岗位数据
            jobs = Joblist.objects.filter(filters).order_by('-time')
            # 分页
            from django.core.paginator import Paginator
            paginator = Paginator(jobs, page_size)

            if current_page < 1:
                current_page = 1
            elif current_page > paginator.num_pages:
                current_page = paginator.num_pages

            current_page_obj = paginator.page(current_page)

            # 序列化岗位数据
            # 序列化岗位数据
            job_list = []
            for job in current_page_obj.object_list:
                # 格式化薪资
                if job.salaryMin is not None:
                    def format_salary(sal):
                        if sal is None:
                            return 0
                        formatted = float(sal)
                        if formatted == int(formatted):
                            return str(int(formatted))
                        else:
                            return f"{formatted:.1f}"

                    min_sal = format_salary(job.salaryMin)
                    max_sal = format_salary(job.salaryMax)
                    salary = f"{min_sal}-{max_sal}k"
                    if job.salaryBonus:
                        salary += f'*{format_salary(job.salaryBonus)}薪'
                else:
                    salary = "薪资面议"

                # 获取公司名称
                company_name = job.company.name if job.company else ''
                company_size = job.company.size if job.company else ''
                company_location = job.company.location if job.company else ''

                # 获取负责人信息
                staff_name = job.staff.realName if job.staff else ''

                # 格式化行业名称
                industry_name = ''
                if job.industry:
                    try:
                        from ..models import Industry
                        code_list = job.industry.split('$')
                        name_list = []
                        for code in code_list:
                            code = code.strip()
                            if code:
                                industry_obj = Industry.objects.get(code=code)
                                name_list.append(industry_obj.name)
                        industry_name = ' > '.join(name_list) if name_list else job.industry
                    except Industry.DoesNotExist:
                        industry_name = job.industry

                # 检查是否已收藏
                is_favorited = Favorite.objects.filter(job=job, user=userInfo).exists()

                job_list.append({
                    'id': job.id,
                    'title': job.name,
                    'company': company_name,
                    'companyId': job.company.id if job.company else None,
                    'companySize': company_size,
                    'companyLocation': company_location,
                    'city': job.city,
                    'salary': salary,
                    'salaryMin': float(job.salaryMin) if job.salaryMin else 0,
                    'salaryMax': float(job.salaryMax) if job.salaryMax else 0,
                    'salaryBonus': job.salaryBonus,
                    'education': job.edu,
                    'experience': job.exp,
                    'industry': industry_name,
                    'industryCode': job.industry,
                    'jobType': job.type,
                    'headcount': job.num,
                    'tags': job.tags.split(',') if job.tags else [],
                    'description': job.content,
                    'keyList': job.keyList,
                    'urgency': job.urgency,
                    'status': job.status,
                    'staff': staff_name,
                    'staffId': job.staff.id if job.staff else None,
                    'publishTime': job.time.strftime('%Y-%m-%d %H:%M:%S') if job.time else '',
                    'delete': job.delete,
                    'isFavorited': is_favorited,
                })

            # 构建页码范围
            page_range = []
            visible_number = 10
            min_page = max(1, current_page - visible_number // 2)
            max_page = min(paginator.num_pages + 1, min_page + visible_number)
            if max_page > paginator.num_pages:
                min_page = max(1, max_page - visible_number)

            for i in range(min_page, max_page):
                page_range.append(i)

            return JsonResponse({
                'code': 200,
                'msg': '获取数据成功',
                'data': {
                    'userInfo': {
                        'userId': userInfo.id,
                        'username': userInfo.username,
                        'realName': userInfo.realName,
                        'email': userInfo.email,
                    },
                    'jobs': job_list,
                    'pagination': {
                        'current': current_page,
                        'current_page': current_page,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                        'items_per_page': page_size,
                        'size': page_size,
                        'page_range': page_range
                    }
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
            logger.error(f"获取表格数据失败: {e}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'msg': f'获取数据失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='jobDetail')
    def getJobDetailForTalent(self, request):
        try:
            id = request.data.get('id')
            if not id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少职位ID',
                    'data': None
                }, status=400)
            
            username = request.session.get('username')
            if not username:
                return JsonResponse({
                    'code': 401,
                    'msg': '未登录',
                    'data': None
                }, status=401)
            
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'msg': '用户不存在',
                    'data': None
                }, status=404)
            
            job = Joblist.objects.get(id=id, delete=0)
            
            # 记录浏览历史
            try:
                history = History.objects.get(job=job, user=user)
                history.count += 1
                history.save()
            except History.DoesNotExist:
                History.objects.create(
                    job=job,
                    user=user,
                    count=1
                )
            
            def format_salary(sal):
                if sal is None:
                    return 0
                formatted = float(sal)
                if formatted == int(formatted):
                    return str(int(formatted))
                else:
                    return f"{formatted:.1f}"

            if job.salaryMin is not None:
                min_sal = format_salary(job.salaryMin)
                max_sal = format_salary(job.salaryMax)
                salary = f"{min_sal}-{max_sal}k"
                if job.salaryBonus:
                    salary += f'*{format_salary(job.salaryBonus)}薪'
            else:
                salary = "薪资面议"
            company_name = job.company.name if job.company else ''
            company_size = job.company.size if job.company else ''
            company_location = job.company.location if job.company else ''
            company_content = job.company.content if job.company else ''
            staff_name = job.staff.realName if job.staff else ''

            industry_name = ''
            if job.industry:
                try:
                    from ..models import Industry
                    code_list = job.industry.split('$')
                    name_list = []
                    for code in code_list:
                        code = code.strip()
                        if code:
                            industry_obj = Industry.objects.get(code=code)
                            name_list.append(industry_obj.name)
                    industry_name = ' > '.join(name_list) if name_list else job.industry
                except Industry.DoesNotExist:
                    industry_name = job.industry

            # 检查是否已收藏
            is_favorited = Favorite.objects.filter(job=job, user=user).exists()

            job_data = {
                'id': job.id,
                'title': job.name,
                'company': company_name,
                'companyId': job.company.id if job.company else None,
                'companySize': company_size,
                'companyLocation': company_location,
                'companyDescription': company_content,
                'city': job.city,
                'industry': industry_name,
                'industryCode': job.industry,
                'education': job.edu,
                'experience': job.exp,
                'salaryMin': float(job.salaryMin) if job.salaryMin else 0,
                'salaryMax': float(job.salaryMax) if job.salaryMax else 0,
                'salaryBonus': job.salaryBonus,
                'salary': salary,
                'jobType': job.type,
                'headcount': job.num,
                'description': job.content,
                'tags': job.tags.split(',') if job.tags else [],
                'staff': staff_name,
                'staffId': job.staff.id if job.staff else None,
                'recruiterAvatar': job.staff.avatar.url if job.staff and job.staff.avatar else '',
                'status': job.status,
                'urgency': job.urgency,
                'publishTime': job.time.strftime('%Y-%m-%d %H:%M:%S') if job.time else '',
                'delete': job.delete,
                'isFavorited': is_favorited,
            }

            return JsonResponse({
                'code': 200,
                'msg': '获取职位详情成功',
                'data': job_data
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '职位不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取职位详情失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'获取职位详情失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def eduOptions(self, request):
        educations = ["不限", "初中及以下", "高中", "中专/中技", "大专", "本科", "硕士", "MBA/EMBA", "博士"]
        return JsonResponse({
            'code': 200,
            'msg': '获取成功',
            'data': educations
        }, status=200)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def expOptions(self, request):
        work_experiences = ["不限", "无经验", "1年以下", "1-3年", "3-5年", "5-10年", "10年以上"]
        return JsonResponse({
            'code': 200,
            'msg': '获取成功',
            'data': work_experiences
        }, status=200)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def salary(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            userInfo = User.objects.get(username=username)
            edu_exp_cache_key = f"salary_education_experience"
            bonus_cache_key = f"salary_bonus"
            cached_edu_exp = cache.get(edu_exp_cache_key)
            cached_bonus = cache.get(bonus_cache_key)

            if cached_edu_exp is None:
                from ..utils import getSalaryCharData
                educations, workExp, barData = getSalaryCharData.getEduForEpx()
                lineData = workExp + ["最低薪资", "平均薪资", "最高薪资"]
                lineDa = educations + ["最低薪资", "平均薪资", "最高薪资"]
                cache.set(edu_exp_cache_key, {
                    'educations': educations,
                    'workExp': workExp,
                    'barData': barData,
                    'lineData': lineData,
                    'lineDa': lineDa
                }, 1800)
                cached_data = {
                    'educations': educations,
                    'workExp': workExp,
                    'barData': barData,
                    'lineData': lineData,
                    'lineDa': lineDa
                }
            else:
                cached_data = cached_edu_exp

            if cached_bonus is None:
                from ..utils import getSalaryCharData
                BonusData = getSalaryCharData.getBonusData()
                cache.set(bonus_cache_key, BonusData, 1800)
                cached_bonus_data = BonusData
            else:
                cached_bonus_data = cached_bonus

            return JsonResponse({
                'code': 200,
                'msg': '获取薪资数据成功',
                'data': {
                    'userInfo': {
                        'userId': userInfo.id,
                        'username': userInfo.username,
                        'realName': userInfo.realName,
                    },
                    'educations': cached_data['educations'],
                    'workExp': cached_data['workExp'],
                    'barData': cached_data['barData'],
                    'lineData': cached_data['lineData'],
                    'lineDa': cached_data['lineDa'],
                    'BonusData': cached_bonus_data
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
            logger.error(f"获取薪资数据失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取数据失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def company(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            userInfo = User.objects.get(username=username)
            pie_cache_key = f"company_pie"
            people_cache_key = f"company_people"
            cached_pie = cache.get(pie_cache_key)
            cached_people = cache.get(people_cache_key)

            if cached_pie is None:
                from ..utils import getCompanyCharData
                pieData = getCompanyCharData.getCompanyPie()
                cache.set(pie_cache_key, pieData, 1800)
                cached_pie_data = pieData
            else:
                cached_pie_data = cached_pie

            if cached_people is None:
                from ..utils import getCompanyCharData
                companySizes, lineData = getCompanyCharData.getCompanyPeople()
                cache.set(people_cache_key, {
                    'companySizes': companySizes,
                    'lineData': lineData
                }, 1800)
                cached_people_data = {
                    'companySizes': companySizes,
                    'lineData': lineData
                }
            else:
                cached_people_data = cached_people

            return JsonResponse({
                'code': 200,
                'msg': '获取公司数据成功',
                'data': {
                    'userInfo': {
                        'userId': userInfo.id,
                        'username': userInfo.username,
                        'realName': userInfo.realName,
                    },
                    'pieData': cached_pie_data,
                    'companySizes': cached_people_data['companySizes'],
                    'lineData': cached_people_data['lineData']
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
            logger.error(f"获取公司数据失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取数据失败，请稍后重试',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def positionList(self, request):
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
            from django.core.paginator import Paginator
            employer = Employer.objects.get(username=username)
            employer_id = employer.id
            company_id = employer.company
            if not company_id:
                return JsonResponse({
                    'code': 404,
                    'msg': '未关联公司，无法查看岗位',
                    'data': None
                }, status=404)
            # 查询条件：公司匹配 且 staff（创建者）是当前招聘者
            jobs = Joblist.objects.filter(
                company_id=company_id,
                staff_id=employer_id,
                delete=0
            ).order_by('-id')
            current_page_num = int(request.GET.get('current', request.GET.get('page', 1)))
            page_size = int(request.GET.get('size', request.GET.get('pageSize', 10)))

            paginator = Paginator(jobs, page_size)
            # 确保页码在有效范围内
            if current_page_num < 1:
                current_page_num = 1
            elif current_page_num > paginator.num_pages:
                current_page_num = paginator.num_pages
            current_page = paginator.page(current_page_num)
            # 序列化岗位数据
            job_list = []
            for job in current_page.object_list:
                industry_name = job.industry
                if job.industry:
                    try:
                        # 按 $ 分割层级代码
                        code_list = job.industry.split('$')
                        name_list = []
                        for code in code_list:
                            code = code.strip()
                            if code:
                                industry_obj = Industry.objects.get(code=code)
                                name_list.append(industry_obj.name)
                        industry_name = ' > '.join(name_list) if name_list else job.industry
                    except Industry.DoesNotExist:
                        industry_name = job.industry

                company_name = job.company.name if job.company else ''
                staff_name = job.staff.realName if job.staff else ''

                # 统计数据
                views_count = History.objects.filter(job=job).count()
                applications_count = Application.objects.filter(job=job).count()
                favorites_count = Favorite.objects.filter(job=job).count()
                # 优质候选人：面试通过的候选人数量
                candidates_count = Application.objects.filter(
                    job=job,
                    status='finalPass'
                ).count()

                job_data = {
                    'id': job.id,
                    'name': job.name,
                    'salaryMin': float(job.salaryMin),
                    'salaryMax': float(job.salaryMax),
                    'salaryBonus': job.salaryBonus,
                    'city': job.city,
                    'exp': job.exp,
                    'edu': job.edu,
                    'industry': industry_name,
                    'industryCode': job.industry,
                    'num': job.num,
                    'tags': job.tags,
                    'type': job.type,
                    'content': job.content,
                    'time': job.time.strftime('%Y-%m-%d %H:%M:%S'),
                    'urgency': job.urgency,
                    'status': job.status,
                    'company': company_name,
                    'staff': staff_name,
                    'views': views_count,
                    'applications': applications_count,
                    'favorites': favorites_count,
                    'candidates': candidates_count,
                }

                job_list.append(job_data)

            return JsonResponse({
                'code': 200,
                'msg': '获取岗位列表成功',
                'data': {
                    'jobs': job_list,
                    'pagination': {
                        'current': current_page_num,
                        'current_page': current_page_num,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                        'items_per_page': page_size,
                        'size': page_size
                    }
                }
            }, status=200)

        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取岗位列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({
                'code': 500,
                'msg': f'获取岗位列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='create')
    def createJob(self, request):
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
            employer = Employer.objects.get(username=username)
            required_fields = ['jobName', 'salaryMin', 'salaryMax', 'location', 'experience', 'education']
            for field in required_fields:
                if field not in request.data or not request.data[field]:
                    return JsonResponse({
                        'code': 400,
                        'msg': f'缺少必填字段: {field}',
                        'data': None
                    }, status=400)
            # 创建岗位
            job = Joblist.objects.create(
                name=request.data.get('jobName'),
                salaryMin=float(request.data.get('salaryMin', 0)),
                salaryMax=float(request.data.get('salaryMax', 0)),
                salaryBonus=int(request.data.get('salaryBonus', 0)),
                city=request.data.get('location', ''),
                exp=request.data.get('experience', ''),
                edu=request.data.get('education', ''),
                industry=request.data.get('industry', ''),
                num=int(request.data.get('headcount', 1)),
                tags=request.data.get('allWelfare', ''),
                type=request.data.get('jobType', ''),
                content=request.data.get('description', ''),
                urgency=request.data.get('urgency', ''),
                status=request.data.get('status', ''),
                company_id=employer.company,
                staff_id=employer.id
            )

            return JsonResponse({
                'code': 200,
                'msg': '岗位创建成功',
                'data': {
                    'id': job.id,
                    'name': job.name,
                    'company': job.company.name if job.company else employer.comName,
                    'createTime': job.time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }, status=200)

        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"创建岗位失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'创建岗位失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'], url_path='update')
    def updateJob(self, request):
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
            employer = Employer.objects.get(username=username)
            id = request.data.get('id')
            job = Joblist.objects.get(id=id)
            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权修改此岗位',
                    'data': None
                }, status=403)
            # 前后端字段名映射
            field_mapping = {
                'jobName': 'name',
                'location': 'city',
                'experience': 'exp',
                'education': 'edu',
                'headcount': 'num',
                'allWelfare': 'tags',
                'jobType': 'type',
                'description': 'content'
            }
            float_fields = ['salaryMin', 'salaryMax']
            int_fields = ['salaryBonus', 'num', 'headcount']

            for front_field, back_field in field_mapping.items():
                if front_field in request.data:
                    value = request.data[front_field]
                    if back_field in int_fields:
                        value = int(value) if value else 0
                    setattr(job, back_field, value)

            for field in ['salaryMin', 'salaryMax', 'salaryBonus']:
                if field in request.data:
                    value = request.data[field]
                    if field in float_fields:
                        value = float(value) if value else 0.0
                    elif field in int_fields:
                        value = int(value) if value else 0
                    setattr(job, field, value)

            job.save()

            return JsonResponse({
                'code': 200,
                'msg': '岗位更新成功',
                'data': {
                    'id': job.id,
                    'name': job.name,
                    'updateTime': job.time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新岗位失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'更新岗位失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='detail')
    def getJobDetail(self, request):
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
            employer = Employer.objects.get(username=username)
            id = request.data.get('id')
            job = Joblist.objects.get(id=id)
            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权查看此岗位',
                    'data': None
                }, status=403)
            job_data = {
                'id': job.id,
                'name': job.name,
                'salaryMin': float(job.salaryMin),
                'salaryMax': float(job.salaryMax),
                'salaryBonus': job.salaryBonus,
                'city': job.city,
                'exp': job.exp,
                'edu': job.edu,
                'industry': job.industry,
                'industryCode': job.industry,
                'num': job.num,
                'tags': job.tags,
                'type': job.type,
                'content': job.content,
                'urgency': job.urgency,
                'status': job.status,
                'time': job.time.strftime('%Y-%m-%d %H:%M:%S'),
                'companyId': job.company.id if job.company else None,
                'companyName': job.company.name if job.company else '',
                'staffId': job.staff.id if job.staff else None,
                'staffName': job.staff.realName if job.staff else '',
            }

            return JsonResponse({
                'code': 200,
                'msg': '获取岗位详情成功',
                'data': job_data
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"获取岗位详情失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'获取岗位详情失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'], url_path='toggleStatus')
    def toggleJobStatus(self, request):
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
            employer = Employer.objects.get(username=username)
            id = request.data.get('id')
            job = Joblist.objects.get(id=id)
            # 验证权限：只能操作自己公司的岗位
            if job.company_id != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此岗位',
                    'data': None
                }, status=403)

            new_status = request.data.get('status')
            if not new_status:
                return JsonResponse({
                    'code': 400,
                    'msg': '请提供状态值',
                    'data': None
                }, status=400)
            job.status = new_status
            job.save()
            return JsonResponse({
                'code': 200,
                'msg': f'岗位{new_status}',
                'data': {
                    'id': job.id,
                    'status': job.status
                }
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"切换岗位状态失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'操作失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'], url_path='toggleClose')
    def toggleCloseStatus(self, request):
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
            employer = Employer.objects.get(username=username)
            id = request.data.get('id')
            job = Joblist.objects.get(id=id)

            if job.company_id != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此岗位',
                    'data': None
                }, status=403)
            new_status = request.data.get('status')
            if not new_status:
                return JsonResponse({
                    'code': 400,
                    'msg': '请提供状态值',
                    'data': None
                }, status=400)
            job.status = new_status
            job.save()
            return JsonResponse({
                'code': 200,
                'msg': f'岗位{new_status}',
                'data': {
                    'id': job.id,
                    'status': job.status
                }
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"切换关闭状态失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'操作失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['delete'], url_path='delete')
    def deleteJob(self, request):
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
            employer = Employer.objects.get(username=username)
            id = request.data.get('id')
            job = Joblist.objects.get(id=id)
            if job.company_id != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权删除此岗位',
                    'data': None
                }, status=403)
            job.delete = 1
            job.save()

            return JsonResponse({
                'code': 200,
                'msg': '岗位删除成功',
                'data': {
                    'id': job.id,
                    'name': job.name
                }
            }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except Employer.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"删除岗位失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'删除失败: {str(e)}',
                'data': None
            }, status=500)
    @action(detail=False, methods=['post'], url_path='favorite')
    def favoriteJob(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            user = User.objects.get(username=username)
            job_id = request.data.get('id')

            if not job_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少岗位ID',
                    'data': None
                }, status=400)

            job = Joblist.objects.get(id=job_id, delete=0)

            # 创建收藏记录（如果已存在则忽略）
            favorite, created = Favorite.objects.get_or_create(
                job=job,
                user=user
            )

            if created:
                return JsonResponse({
                    'code': 200,
                    'msg': '收藏成功',
                    'data': {
                        'id': favorite.id,
                        'jobId': job.id,
                        'jobName': job.name
                    }
                }, status=200)
            else:
                return JsonResponse({
                    'code': 200,
                    'msg': '已收藏',
                    'data': {
                        'id': favorite.id,
                        'jobId': job.id,
                        'jobName': job.name
                    }
                }, status=200)

        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '岗位不存在',
                'data': None
            }, status=404)
        except User.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"收藏岗位失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'收藏失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='unfavorite')
    def unfavoriteJob(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            user = User.objects.get(username=username)
            job_id = request.data.get('id')

            if not job_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少岗位ID',
                    'data': None
                }, status=400)

            # 删除收藏记录
            deleted_count, _ = Favorite.objects.filter(
                job_id=job_id,
                user=user
            ).delete()

            if deleted_count > 0:
                return JsonResponse({
                    'code': 200,
                    'msg': '取消收藏成功',
                    'data': None
                }, status=200)
            else:
                return JsonResponse({
                    'code': 200,
                    'msg': '未收藏该岗位',
                    'data': None
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
            logger.error(f"取消收藏失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'取消收藏失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], url_path='favoriteList')
    def getFavoriteJobs(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            user = User.objects.get(username=username)

            # 获取筛选参数
            work = request.GET.get('work', '')
            city = request.GET.get('city', '')
            industry = request.GET.get('industry', '')
            education = request.GET.get('education', '不限')
            experience = request.GET.get('experience', '不限')
            salary_min = request.GET.get('salaryMin', '')
            company_size = request.GET.get('companySize', '')
            job_types = request.GET.get('jobTypes', '')

            # 分页参数
            current_page = int(request.GET.get('current', request.GET.get('page', 1)))
            page_size = int(request.GET.get('size', request.GET.get('pageSize', 10)))

            # 获取用户的收藏记录
            favorites = Favorite.objects.filter(user=user).order_by('-id')

            # 获取收藏的岗位ID列表
            job_ids = [fav.job_id for fav in favorites]

            # 构建查询条件
            from django.db.models import Q
            filters = Q(id__in=job_ids) & Q(delete=0)

            if work:
                filters &= Q(name__icontains=work) | Q(keyList__icontains=work)
            if city:
                filters &= Q(city__icontains=city)
            if industry:
                if industry.endswith('_child'):
                    parent_code = industry.replace('_child', '')
                    filters &= Q(industry__startswith=parent_code)
                else:
                    filters &= Q(industry__icontains=industry)
            if education and education != '不限':
                filters &= Q(edu=education)
            if experience and experience != '不限':
                filters &= Q(exp=experience)
            if salary_min:
                try:
                    filters &= Q(salaryMin__gte=float(salary_min))
                except ValueError:
                    pass
            if company_size:
                filters &= Q(comSize=company_size)
            if job_types:
                types_list = job_types.split(',')
                type_filter = Q()
                for job_type in types_list:
                    type_filter |= Q(type__icontains=job_type.strip())
                filters &= type_filter

            # 获取岗位数据
            jobs = Joblist.objects.filter(filters).order_by('-time')
            paginator = Paginator(jobs, page_size)

            if current_page < 1:
                current_page = 1
            elif current_page > paginator.num_pages:
                current_page = paginator.num_pages

            current_page_obj = paginator.page(current_page)

            # 序列化岗位数据（与joblist方法相同的格式）
            job_list = []
            for job in current_page_obj.object_list:
                if job.salaryMin is not None:
                    def format_salary(sal):
                        if sal is None:
                            return 0
                        formatted = float(sal)
                        if formatted == int(formatted):
                            return str(int(formatted))
                        else:
                            return f"{formatted:.1f}"

                    min_sal = format_salary(job.salaryMin)
                    max_sal = format_salary(job.salaryMax)
                    salary = f"{min_sal}-{max_sal}k"
                    if job.salaryBonus:
                        salary += f'*{format_salary(job.salaryBonus)}薪'
                else:
                    salary = "薪资面议"

                company_name = job.company.name if job.company else ''
                company_size = job.company.size if job.company else ''
                company_location = job.company.location if job.company else ''
                staff_name = job.staff.realName if job.staff else ''

                industry_name = ''
                if job.industry:
                    try:
                        code_list = job.industry.split('$')
                        name_list = []
                        for code in code_list:
                            code = code.strip()
                            if code:
                                industry_obj = Industry.objects.get(code=code)
                                name_list.append(industry_obj.name)
                        industry_name = ' > '.join(name_list) if name_list else job.industry
                    except Industry.DoesNotExist:
                        industry_name = job.industry

                # 收藏列表中的岗位都是已收藏状态
                job_list.append({
                    'id': job.id,
                    'title': job.name,
                    'company': company_name,
                    'companyId': job.company.id if job.company else None,
                    'companySize': company_size,
                    'companyLocation': company_location,
                    'city': job.city,
                    'salary': salary,
                    'salaryMin': float(job.salaryMin) if job.salaryMin else 0,
                    'salaryMax': float(job.salaryMax) if job.salaryMax else 0,
                    'salaryBonus': job.salaryBonus,
                    'education': job.edu,
                    'experience': job.exp,
                    'industry': industry_name,
                    'industryCode': job.industry,
                    'jobType': job.type,
                    'headcount': job.num,
                    'tags': job.tags.split(',') if job.tags else [],
                    'description': job.content,
                    'keyList': job.keyList,
                    'urgency': job.urgency,
                    'status': job.status,
                    'staff': staff_name,
                    'staffId': job.staff.id if job.staff else None,
                    'publishTime': job.time.strftime('%Y-%m-%d %H:%M:%S') if job.time else '',
                    'delete': job.delete,
                    'isFavorited': True,
                })

            # 构建页码范围
            page_range = []
            visible_number = 10
            min_page = max(1, current_page - visible_number // 2)
            max_page = min(paginator.num_pages + 1, min_page + visible_number)
            if max_page > paginator.num_pages:
                min_page = max(1, max_page - visible_number)

            for i in range(min_page, max_page):
                page_range.append(i)

            return JsonResponse({
                'code': 200,
                'msg': '获取收藏列表成功',
                'data': {
                    'jobs': job_list,
                    'pagination': {
                        'current': current_page,
                        'current_page': current_page,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                        'items_per_page': page_size,
                        'size': page_size,
                        'page_range': page_range
                    }
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
            logger.error(f"获取收藏列表失败: {e}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'msg': f'获取收藏列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], url_path='viewHistory')
    def getViewHistory(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            user = User.objects.get(username=username)

            # 获取筛选参数
            work = request.GET.get('work', '')
            city = request.GET.get('city', '')
            industry = request.GET.get('industry', '')
            education = request.GET.get('education', '不限')
            experience = request.GET.get('experience', '不限')
            salary_min = request.GET.get('salaryMin', '')
            company_size = request.GET.get('companySize', '')
            job_types = request.GET.get('jobTypes', '')

            # 分页参数
            current_page = int(request.GET.get('current', request.GET.get('page', 1)))
            page_size = int(request.GET.get('size', request.GET.get('pageSize', 10)))

            # 获取用户的浏览历史记录
            histories = History.objects.filter(user=user).order_by('-id')

            # 获取浏览的岗位ID列表
            job_ids = [hist.job_id for hist in histories]

            # 构建查询条件
            from django.db.models import Q
            filters = Q(id__in=job_ids) & Q(delete=0)

            if work:
                filters &= Q(name__icontains=work) | Q(keyList__icontains=work)
            if city:
                filters &= Q(city__icontains=city)
            if industry:
                if industry.endswith('_child'):
                    parent_code = industry.replace('_child', '')
                    filters &= Q(industry__startswith=parent_code)
                else:
                    filters &= Q(industry__icontains=industry)
            if education and education != '不限':
                filters &= Q(edu=education)
            if experience and experience != '不限':
                filters &= Q(exp=experience)
            if salary_min:
                try:
                    filters &= Q(salaryMin__gte=float(salary_min))
                except ValueError:
                    pass
            if company_size:
                filters &= Q(comSize=company_size)
            if job_types:
                types_list = job_types.split(',')
                type_filter = Q()
                for job_type in types_list:
                    type_filter |= Q(type__icontains=job_type.strip())
                filters &= type_filter

            # 获取岗位数据
            jobs = Joblist.objects.filter(filters).order_by('-time')
            paginator = Paginator(jobs, page_size)

            if current_page < 1:
                current_page = 1
            elif current_page > paginator.num_pages:
                current_page = paginator.num_pages

            current_page_obj = paginator.page(current_page)

            # 序列化岗位数据（与joblist方法相同的格式）
            job_list = []
            for job in current_page_obj.object_list:
                if job.salaryMin is not None:
                    def format_salary(sal):
                        if sal is None:
                            return 0
                        formatted = float(sal)
                        if formatted == int(formatted):
                            return str(int(formatted))
                        else:
                            return f"{formatted:.1f}"

                    min_sal = format_salary(job.salaryMin)
                    max_sal = format_salary(job.salaryMax)
                    salary = f"{min_sal}-{max_sal}k"
                    if job.salaryBonus:
                        salary += f'*{format_salary(job.salaryBonus)}薪'
                else:
                    salary = "薪资面议"

                company_name = job.company.name if job.company else ''
                company_size = job.company.size if job.company else ''
                company_location = job.company.location if job.company else ''
                staff_name = job.staff.realName if job.staff else ''

                industry_name = ''
                if job.industry:
                    try:
                        code_list = job.industry.split('$')
                        name_list = []
                        for code in code_list:
                            code = code.strip()
                            if code:
                                industry_obj = Industry.objects.get(code=code)
                                name_list.append(industry_obj.name)
                        industry_name = ' > '.join(name_list) if name_list else job.industry
                    except Industry.DoesNotExist:
                        industry_name = job.industry

                job_list.append({
                    'id': job.id,
                    'title': job.name,
                    'company': company_name,
                    'companyId': job.company.id if job.company else None,
                    'companySize': company_size,
                    'companyLocation': company_location,
                    'city': job.city,
                    'salary': salary,
                    'salaryMin': float(job.salaryMin) if job.salaryMin else 0,
                    'salaryMax': float(job.salaryMax) if job.salaryMax else 0,
                    'salaryBonus': job.salaryBonus,
                    'education': job.edu,
                    'experience': job.exp,
                    'industry': industry_name,
                    'industryCode': job.industry,
                    'jobType': job.type,
                    'headcount': job.num,
                    'tags': job.tags.split(',') if job.tags else [],
                    'description': job.content,
                    'keyList': job.keyList,
                    'urgency': job.urgency,
                    'status': job.status,
                    'staff': staff_name,
                    'staffId': job.staff.id if job.staff else None,
                    'publishTime': job.time.strftime('%Y-%m-%d %H:%M:%S') if job.time else '',
                    'delete': job.delete,
                })

            # 构建页码范围
            page_range = []
            visible_number = 10
            min_page = max(1, current_page - visible_number // 2)
            max_page = min(paginator.num_pages + 1, min_page + visible_number)
            if max_page > paginator.num_pages:
                min_page = max(1, max_page - visible_number)

            for i in range(min_page, max_page):
                page_range.append(i)

            return JsonResponse({
                'code': 200,
                'msg': '获取浏览历史成功',
                'data': {
                    'jobs': job_list,
                    'pagination': {
                        'current': current_page,
                        'current_page': current_page,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                        'items_per_page': page_size,
                        'size': page_size,
                        'page_range': page_range
                    }
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
            logger.error(f"获取浏览历史失败: {e}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'msg': f'获取浏览历史失败: {str(e)}',
                'data': None
            }, status=500)
