# myApp/api_views/application_views.py
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import models
from ..models import Application, InterviewStage, Joblist, Employer, User
from ..serializers import ApplicationListSerializer, InterviewStageSerializer


class ApplicationViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'], url_path='apply', permission_classes=[permissions.AllowAny])
    def apply_job(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            job_id = request.data.get('id')
            if not job_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少职位ID',
                    'data': None
                }, status=400)
            user = User.objects.get(username=username)
            job = Joblist.objects.get(id=job_id, delete=0)
            if job.status == 'closed':
                return JsonResponse({
                    'code': 400,
                    'msg': '该职位已关闭，无法投递',
                    'data': None
                }, status=400)
            if job.num <= 0:
                return JsonResponse({
                    'code': 400,
                    'msg': '该职位名额已满，无法投递',
                    'data': None
                }, status=400)
            existing_application = Application.objects.filter(
                job=job,
                user=user
            ).first()
            if existing_application:
                if existing_application.status == 'archived':
                    existing_application.status = 'pending'
                    existing_application.applyTime = timezone.now()
                    existing_application.viewTime = None
                    existing_application.interviewTime = None
                    existing_application.feedback = ''
                    existing_application.tags = ''
                    existing_application.save()
                    return JsonResponse({
                        'code': 200,
                        'msg': '重新投递成功',
                        'data': {
                            'id': existing_application.id,
                            'status': existing_application.status,
                            'applyTime': existing_application.applyTime.strftime('%Y-%m-%d %H:%M:%S')
                        }
                    }, status=200)
                else:
                    status_map = {
                        'pending': '待处理',
                        'viewed': '已查看',
                        'interviewing': '面试中',
                        'finalPass': '面试通过',
                        'hired': '已录用'
                    }
                    status_text = status_map.get(existing_application.status, '处理中')
                    return JsonResponse({
                        'code': 400,
                        'msg': f'您已投递过该职位，当前状态：{status_text}',
                        'data': {
                            'id': existing_application.id,
                            'status': existing_application.status
                        }
                    }, status=400)
            employer = Employer.objects.filter(company=job.company).first()
            if not employer:
                return JsonResponse({
                    'code': 404,
                    'msg': '该职位暂无招聘负责人',
                    'data': None
                }, status=404)
            application = Application.objects.create(
                job=job,
                user=user,
                employer=employer,
                status='pending',
                applyTime=timezone.now()
            )
            return JsonResponse({
                'code': 200,
                'msg': '投递成功',
                'data': {
                    'id': application.id,
                    'status': application.status,
                    'applyTime': application.applyTime.strftime('%Y-%m-%d %H:%M:%S'),
                    'jobName': job.name,
                    'companyName': job.company.name if job.company else ''
                }
            }, status=200)
        except User.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '用户不存在',
                'data': None
            }, status=404)
        except Joblist.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '职位不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"投递简历失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({
                'code': 500,
                'msg': f'投递失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], url_path='list')
    def list_applications(self, request):
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
            page = int(request.GET.get('page', 1))
            size = int(request.GET.get('size', 10))
            keyword = request.GET.get('keyword', '')
            position = request.GET.get('position', '')
            status = request.GET.get('status', '')
            apply_time = request.GET.get('applyTime', '')

            # 查询当前招聘者公司的申请记录
            applications = Application.objects.filter(
                job__company=employer.company
            ).select_related('job', 'user', 'employer').prefetch_related('stages').order_by('-applyTime')

            if keyword:
                user_ids = User.objects.filter(
                    models.Q(realName__icontains=keyword) |
                    models.Q(mobile__icontains=keyword) |
                    models.Q(email__icontains=keyword)
                ).values_list('id', flat=True)
                applications = applications.filter(user__in=user_ids)

            if position:
                job_ids = Joblist.objects.filter(name__icontains=position).values_list('id', flat=True)
                applications = applications.filter(job__in=job_ids)
            if status:
                applications = applications.filter(status=status)
            if apply_time:
                applications = applications.filter(applyTime__date=apply_time)

            paginator = Paginator(applications, size)
            if page < 1:
                page = 1
            elif page > paginator.num_pages:
                page = paginator.num_pages

            current_page = paginator.page(page)

            serializer = ApplicationListSerializer(
                current_page.object_list,
                many=True,
                context={'request': request}
            )

            # 统计各状态数量
            all_apps = Application.objects.filter(
                job__in=Joblist.objects.filter(company=employer.company)
            )
            counts = {
                'pending': all_apps.filter(status='pending').count(),
                'viewed': all_apps.filter(status='viewed').count(),
                'interviewing': all_apps.filter(status='interviewing').count(),
                'finalPass': all_apps.filter(status='finalPass').count(),
                'hired': all_apps.filter(status='hired').count(),
                'archived': all_apps.filter(status='archived').count(),
                'rejected': all_apps.filter(status='rejected').count(),
            }

            return JsonResponse({
                'code': 200,
                'msg': '获取申请列表成功',
                'data': {
                    'applications': serializer.data,
                    'pagination': {
                        'current': page,
                        'current_page': page,
                        'total': paginator.count,
                        'total_pages': paginator.num_pages,
                        'size': size
                    },
                    'counts': counts
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
            logger.error(f"获取申请列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({
                'code': 500,
                'msg': f'获取申请列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['put'], url_path='updateStatus')
    def update_status(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)
        try:
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            new_status = request.data.get('status')
            if not app_id or not new_status:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少必要参数',
                    'data': None
                }, status=400)
            application = Application.objects.get(id=app_id)
            job = application.job
            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)
            # 如果是第一次查看，记录查看时间
            if new_status == 'viewed' and not application.viewTime:
                application.viewTime = timezone.now()
            application.status = new_status
            application.save()
            return JsonResponse({
                'code': 200,
                'msg': '状态更新成功',
                'data': {
                    'id': application.id,
                    'status': application.status
                }
            }, status=200)
        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新状态失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'更新失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='arrangeInterview')
    def arrange_interview(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)

        try:
            import datetime
            from django.utils import timezone
            
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            stage = request.data.get('stage')
            time_str = request.data.get('time')
            data = request.data.get('data', '')

            if not app_id or not stage or not time_str:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少必要参数',
                    'data': None
                }, status=400)

            naive_dt = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            aware_dt = timezone.make_aware(naive_dt)

            application = Application.objects.get(id=app_id)
            job = application.job

            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)

            interview_stage = InterviewStage.objects.create(
                application=application,
                stage=stage,
                time=aware_dt,
                data=data
            )

            application.status = 'interviewing'
            application.interviewTime = aware_dt
            application.save()

            return JsonResponse({
                'code': 200,
                'msg': '面试安排成功',
                'data': {
                    'stage_id': interview_stage.id,
                    'stage': interview_stage.stage,
                    'time': aware_dt.strftime('%Y-%m-%d %H:%M:%S')
                }
            }, status=200)

        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"安排面试失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'安排失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='submitEvaluation')
    def submit_evaluation(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)
        try:
            from django.db import transaction
            with transaction.atomic():
                employer = Employer.objects.get(username=username)
                app_id = request.data.get('id')
                comment = request.data.get('comment', '')
                passed = request.data.get('passed')
                if not app_id or passed is None:
                    return JsonResponse({
                        'code': 400,
                        'msg': '缺少必要参数',
                        'data': None
                    }, status=400)
                application = Application.objects.get(id=app_id)
                job = application.job
                if job.company != employer.company:
                    return JsonResponse({
                        'code': 403,
                        'msg': '无权操作此申请',
                        'data': None
                    }, status=403)
                latest_stage = application.stages.order_by('-createTime').first()
                if not latest_stage:
                    return JsonResponse({
                        'code': 400,
                        'msg': '没有面试记录',
                        'data': None
                    }, status=400)
                # 更新面试阶段的评价和结果
                latest_stage.comment = comment
                latest_stage.passed = passed
                latest_stage.save()
                if passed:
                    application.status = 'finalPass'
                    application.feedback = comment
                else:
                    # 评价为不通过，状态更新为“已淘汰”
                    application.status = 'archived'
                    application.feedback = f'淘汰原因：{comment}'
                application.save()
                return JsonResponse({
                    'code': 200,
                    'msg': '评价提交成功',
                    'data': {
                        'status': application.status,
                        'next_action': '安排下一轮面试' if passed and latest_stage.stage != 'final' else '完成'
                    }
                }, status=200)
        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"提交评价失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({
                'code': 500,
                'msg': f'提交失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='hire')
    def hire_candidate(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)
        try:
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            application = Application.objects.get(id=app_id)
            job = application.job
            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)
            # 1. 优先检查岗位人数是否已满
            if job.num <= 0:
                job.status = 'closed'
                job.save()
                return JsonResponse({
                    'code': 400,
                    'msg': '该岗位名额已满，无法继续录用',
                    'data': None
                }, status=400)
            application.status = 'hired'
            application.save()
            job.num -= 1
            if job.num == 0:
                job.status = 'closed'
            job.save()

            return JsonResponse({
                'code': 200,
                'msg': '录用成功',
                'data': {
                    'id': application.id,
                    'status': application.status,
                    'job_remaining_num': job.num
                }
            }, status=200)

        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"录用失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'录用失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='reject')
    def reject_candidate(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)

        try:
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            reason = request.data.get('reason', '')

            application = Application.objects.get(id=app_id)
            job = application.job

            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)
            application.status = 'archived'
            if reason:
                application.feedback = f'淘汰原因：{reason}'
            else:
                application.feedback = '已淘汰'
            application.save()

            return JsonResponse({
                'code': 200,
                'msg': '已淘汰该候选人',
                'data': {
                    'id': application.id,
                    'status': application.status,
                    'feedback': application.feedback
                }
            }, status=200)

        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"淘汰失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'淘汰失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='addTag')
    def add_tag(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)

        try:
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            tag = request.data.get('tag', '').strip()
            if not tag:
                return JsonResponse({
                    'code': 400,
                    'msg': '标签不能为空',
                    'data': None
                }, status=400)

            application = Application.objects.get(id=app_id)
            job = application.job

            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)

            # 添加标签（用逗号分隔）
            if application.tags:
                tags_list = [t.strip() for t in application.tags.split(',') if t.strip()]
                if tag not in tags_list:
                    tags_list.append(tag)
                    application.tags = ','.join(tags_list)
            else:
                application.tags = tag

            application.save()

            return JsonResponse({
                'code': 200,
                'msg': '标签添加成功',
                'data': {
                    'tags': application.tags.split(',') if application.tags else []
                }
            }, status=200)

        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"添加标签失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'添加失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='removeTag')
    def remove_tag(self, request):
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
                'msg': '权限不足',
                'data': None
            }, status=403)

        try:
            employer = Employer.objects.get(username=username)
            app_id = request.data.get('id')
            tag = request.data.get('tag', '').strip()
            if not tag:
                return JsonResponse({
                    'code': 400,
                    'msg': '标签不能为空',
                    'data': None
                }, status=400)

            application = Application.objects.get(id=app_id)
            job = application.job

            if job.company != employer.company:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)

            # 移除标签
            if application.tags:
                tags_list = [t.strip() for t in application.tags.split(',') if t.strip()]
                if tag in tags_list:
                    tags_list.remove(tag)
                    application.tags = ','.join(tags_list) if tags_list else ''
                    application.save()

            return JsonResponse({
                'code': 200,
                'msg': '标签移除成功',
                'data': {
                    'tags': application.tags.split(',') if application.tags else []
                }
            }, status=200)

        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
                'data': None
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"移除标签失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'移除失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['get'], url_path='listApply')
    def list_my_applications(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)

        try:
            from django.core.paginator import Paginator
            user = User.objects.get(username=username)
            page = int(request.GET.get('page', 1))
            size = int(request.GET.get('size', 10))
            keyword = request.GET.get('keyword', '')
            status = request.GET.get('status', '')
            apply_time = request.GET.get('applyTime', '')
            # 查询当前求职者的申请记录
            applications = Application.objects.filter(
                user=user
            ).select_related('job', 'employer').prefetch_related('stages').order_by('-applyTime')
            if keyword:
                job_ids = Joblist.objects.filter(name__icontains=keyword).values_list('id', flat=True)
                applications = applications.filter(job__in=job_ids)

            if status:
                applications = applications.filter(status=status)

            if apply_time:
                applications = applications.filter(applyTime__date=apply_time)

            paginator = Paginator(applications, size)
            if page < 1:
                page = 1
            elif page > paginator.num_pages:
                page = paginator.num_pages

            current_page = paginator.page(page)

            serializer = ApplicationListSerializer(
                current_page.object_list,
                many=True,
                context={'request': request}
            )

            # 统计各状态数量
            all_apps = Application.objects.filter(user=user)
            counts = {
                'totalCount': all_apps.count(),
                'pending': all_apps.filter(status='pending').count(),
                'viewed': all_apps.filter(status='viewed').count(),
                'interviewing': all_apps.filter(status='interviewing').count(),
                'finalPass': all_apps.filter(status='finalPass').count(),
                'hired': all_apps.filter(status='hired').count(),
                'archived': all_apps.filter(status='archived').count(),
                'rejected': all_apps.filter(status='rejected').count(),
            }

            return JsonResponse({
                'code': 200,
                'msg': '获取投递列表成功',
                'data': {
                    'applications': serializer.data,
                    'pagination': {
                        'current': page,
                        'current_page': page,
                        'total': paginator.count,
                        'total_pages': paginator.num_pages,
                        'size': size
                    },
                    'counts': counts
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
            logger.error(f"获取投递列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return JsonResponse({
                'code': 500,
                'msg': f'获取投递列表失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='rejectInterview')
    def reject_interview(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)
        try:
            user = User.objects.get(username=username)
            app_id = request.data.get('id')
            if not app_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少申请ID',
                    'data': None
                }, status=400)
            application = Application.objects.get(id=app_id)
            if application.user != user:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)
            if application.status not in ['interviewing', 'finalPass']:
                return JsonResponse({
                    'code': 400,
                    'msg': '当前状态不允许拒绝面试',
                    'data': None
                }, status=400)
            application.status = 'rejected'
            application.feedback = '求职者拒绝面试邀请'
            application.save()
            return JsonResponse({
                'code': 200,
                'msg': '已拒绝面试邀请',
                'data': {
                    'id': application.id,
                    'status': application.status
                }
            }, status=200)
        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
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
            logger.error(f"拒绝面试失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'拒绝失败: {str(e)}',
                'data': None
            }, status=500)

    @action(detail=False, methods=['post'], url_path='rejectHired')
    def reject_hired(self, request):
        username = request.session.get('username')
        if not username:
            return JsonResponse({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }, status=401)
        try:
            user = User.objects.get(username=username)
            app_id = request.data.get('id')
            if not app_id:
                return JsonResponse({
                    'code': 400,
                    'msg': '缺少申请ID',
                    'data': None
                }, status=400)
            application = Application.objects.get(id=app_id)
            if application.user != user:
                return JsonResponse({
                    'code': 403,
                    'msg': '无权操作此申请',
                    'data': None
                }, status=403)
            if application.status != 'hired':
                return JsonResponse({
                    'code': 400,
                    'msg': '当前状态不允许拒绝录用',
                    'data': None
                }, status=400)
            application.status = 'rejected'
            application.feedback = '求职者拒绝录用邀请'
            application.save()
            job = application.job
            job.num += 1
            if job.num > 0 and job.status == 'closed':
                job.status = 'open'
            job.save()
            return JsonResponse({
                'code': 200,
                'msg': '已拒绝录用邀请',
                'data': {
                    'id': application.id,
                    'status': application.status
                }
            }, status=200)
        except Application.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': '申请记录不存在',
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
            logger.error(f"拒绝录用失败: {e}")
            return JsonResponse({
                'code': 500,
                'msg': f'拒绝失败: {str(e)}',
                'data': None
            }, status=500)
