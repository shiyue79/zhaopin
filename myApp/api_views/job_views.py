# myApp/api_views/job_views.py
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django.http import JsonResponse
from django.core.cache import cache
from django.core.paginator import Paginator
from ..models import User, Joblist, Employer, Industry
from ..serializers import JobSerializer
import hashlib
from ..utils import getTableData, getCompanyInfo

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
            pageData = getTableData.getDefaultData(username, request)
            query_params = {
                'work': pageData.get('defaultWork', ''),
                'city': pageData.get('defaultCity', ''),
                'education': pageData.get('defaultEdu', '不限'),
                'experience': pageData.get('defaultExp', '不限'),
                'salary': pageData.get('defaultSalary', ''),
            }
            cache_key = f"table_data_{username}_{hashlib.md5(str(query_params).encode()).hexdigest()}"
            jobs = cache.get(cache_key)
            if jobs is None:
                jobs = getTableData.getTableData(username, pageData)
                cache.set(cache_key, jobs, 1800)

            paginator = Paginator(jobs, 10)
            cur_page = 1
            if request.GET.get('page'):
                cur_page = int(request.GET.get('page'))

            # 确保页码在有效范围内
            if cur_page < 1:
                cur_page = 1
            elif cur_page > paginator.num_pages:
                cur_page = paginator.num_pages

            c_page = paginator.page(cur_page)
            page_range = []
            visibleNumber = 10
            min_page = int(cur_page - visibleNumber / 2)
            if min_page < 1:
                min_page = 1
            max_page = min_page + visibleNumber
            if max_page > paginator.num_pages:
                max_page = paginator.num_pages + 1

            for i in range(min_page, max_page):
                page_range.append(i)

            # 序列化职位数据
            job_list = []
            for job in c_page.object_list:
                if isinstance(job, dict):
                    job_list.append(job)
                else:
                    job_list.append({
                        'id': job.id,
                        'title': job.name,
                        'company': job.company,
                        'city': job.city,
                        'salary': f"{job.salaryMin}-{job.salaryMax}k",
                        'education': job.edu,
                        'experience': job.exp,
                        'description': job.content,
                    })

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
                    'pageData': pageData,
                    'jobs': job_list,
                    'pagination': {
                        'current_page': cur_page,
                        'total_pages': paginator.num_pages,
                        'total_items': paginator.count,
                        'items_per_page': 10,
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
            logger.error(f"获取表格数据失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': '获取数据失败，请稍后重试',
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
                from .utils import getSalaryCharData
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
                from .utils import getSalaryCharData
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
                from .utils import getCompanyCharData
                pieData = getCompanyCharData.getCompanyPie()
                cache.set(pie_cache_key, pieData, 1800)
                cached_pie_data = pieData
            else:
                cached_pie_data = cached_pie

            if cached_people is None:
                from .utils import getCompanyCharData
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
                company=company_id,
                staff=employer_id,
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
                        industry_obj = Industry.objects.get(code=job.industry)
                        industry_name = industry_obj.name
                    except Industry.DoesNotExist:
                        industry_name = job.industry
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
                company=employer.company,
                staff=employer.id
            )

            return JsonResponse({
                'code': 200,
                'msg': '岗位创建成功',
                'data': {
                    'id': job.id,
                    'name': job.name,
                    'company': employer.comName,
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
                'companyId': job.company,
                'staffId': job.staff,
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
            if job.company != employer.company:
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

            if job.company != employer.company:
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
            if job.company != employer.company:
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
