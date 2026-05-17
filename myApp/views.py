import hashlib
from django.http import HttpResponseRedirect
from django.urls import reverse
import urllib.parse
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from myApp.models import User
from myApp.utils import getSelfInfo, getChangePwd, getSalaryCharData, getCompanyCharData, getTableData

def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    else:
        uname = request.POST.get('username')
        pwd = request.POST.get('password')
        if not uname or not pwd:
            return render(request, 'login.html', {
                'errorRes': '用户名和密码不能为空'
            })
        md5 = hashlib.md5()
        md5.update(pwd.encode())
        pwd = md5.hexdigest()
        try:
            user = User.objects.get(username=uname, password=pwd)
            request.session['username'] = user.username
            return redirect('/myApp/selfInfo')
        except User.DoesNotExist:
            return render(request, 'login.html', {
                'errorRes': '用户名或密码不正确'
            })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Login failed for user {uname}: {e}")
            return render(request, 'login.html', {
                'errorRes': '登录失败，请稍后重试'
            })


def logout(request):
    request.session.clear()
    return redirect('login')


def register(request):
    if request.method == 'GET':
        return render(request, 'register.html')
    else:
        uname = request.POST.get('username')
        pwd = request.POST.get('password')
        ckpwd = request.POST.get('checkpassword')
        form_data = {
            'username': uname,
            'password': pwd,
            'checkpassword': ckpwd
        }
        try:
            User.objects.get(username=uname)
        except:
            if not uname or not pwd or not ckpwd:
                return render(request, 'register.html', {
                    'errorRes': '用户名和密码不能为空',
                    'form_data': form_data
                })
            if pwd != ckpwd:
                return render(request, 'register.html', {
                    'errorRes': '两次密码不一致',
                    'form_data': form_data
                })
            md5 = hashlib.md5()
            md5.update(pwd.encode())
            pwd = md5.hexdigest()
            User.objects.create(username=uname, password=pwd)
            return redirect('/myApp/login')
        return render(request, 'register.html', {
            'errorRes': '用户已存在',
            'form_data': form_data
        })


def selfInfo(request):
    uname = request.session.get('username')
    userInfo = User.objects.get(username=uname)
    educations, workEx = getSelfInfo.getPageData()
    if request.method == 'POST':
        getSelfInfo.changeSelfInfo(request.POST, request.FILES)
        userInfo = User.objects.get(username=uname)
    return render(request, 'selfInfo.html', {
        'userInfo': userInfo,
        'pageData': {
            'educations': educations,
            'workEx': workEx
        }
    })


def changePassword(request):
    uname = request.session.get('username')
    userInfo = User.objects.get(username=uname)
    if request.method == 'POST':
        res = getChangePwd.checkPwd(userInfo, request.POST)
        if res != None:
            return render(request, 'changePwd.html', {
                'userInfo': userInfo,
                'errorRes': res
            })
        userInfo = User.objects.get(username=uname)
    return render(request, 'changePwd.html', {
        'userInfo': userInfo
    })


def tableData(request):
    uname = request.session.get('username')
    userInfo = User.objects.get(username=uname)
    pageData = getTableData.getDefaultData(uname, request)
    query_params = {
        'work': pageData.get('defaultWork', ''),
        'city': pageData.get('defaultCity', ''),
        'education': pageData.get('defaultEdu', '不限'),
        'experience': pageData.get('defaultExp', '不限'),
        'salary': pageData.get('defaultSalary', ''),
    }
    cache_key = f"table_data_{uname}_{hashlib.md5(str(query_params).encode()).hexdigest()}"
    jobs = cache.get(cache_key)
    if jobs is None:
        jobs = getTableData.getTableData(uname, pageData)
        cache.set(cache_key, jobs, 1800)
    paginator = Paginator(jobs, 10)
    cur_page = 1
    if request.GET.get('page'):
        cur_page = int(request.GET.get('page'))
    c_page = paginator.page(cur_page)
    page_range = []
    visibleNumber = 10
    min = int(cur_page - visibleNumber / 10)
    if min < 1:
        min = 1
    max = min + visibleNumber
    if max > paginator.page_range[-1]:
        max = paginator.page_range[-1]
    for i in range(min, max):
        page_range.append(i)
    return render(request, 'tableData.html', {
        'userInfo': userInfo,
        'pageData': pageData,
        'jobs': jobs,
        'c_page': c_page,
        'page_range': page_range,
        'paginator': paginator
    })


def salary(request):
    uname = request.session.get('username')
    userInfo = User.objects.get(username=uname)
    edu_exp_cache_key = f"salary_education_experience"
    bonus_cache_key = f"salary_bonus"
    cached_edu_exp = cache.get(edu_exp_cache_key)
    cached_bonus = cache.get(bonus_cache_key)
    if cached_edu_exp is None:
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
        BonusData = getSalaryCharData.getBonusData()
        cache.set(bonus_cache_key, BonusData, 1800)
        cached_bonus_data = BonusData
    else:
        cached_bonus_data = cached_bonus
    # educations, workExp, barData = getSalaryCharData.getEduForEpx()
    # lineData = workExp + ["最低薪资", "平均薪资", "最高薪资"]
    # lineDa = educations + ["最低薪资", "平均薪资", "最高薪资"]
    # BonusData = getSalaryCharData.getBonusData()
    return render(request, 'salaryChar.html', {
        'userInfo': userInfo,
        'educations': cached_data['educations'],
        'workExp': cached_data['workExp'],
        'barData': cached_data['barData'],
        'lineData': cached_data['lineData'],
        'lineDa': cached_data['lineDa'],
        'BonusData': cached_bonus_data
    })


def company(request):
    uname = request.session.get('username')
    userInfo = User.objects.get(username=uname)
    # pieData = getCompanyCharData.getCompanyPie()
    # companySizes, lineData = getCompanyCharData.getCompanyPeople()
    pie_cache_key = f"company_pie"
    people_cache_key = f"company_people"
    cached_pie = cache.get(pie_cache_key)
    cached_people = cache.get(people_cache_key)
    if cached_pie is None:
        pieData = getCompanyCharData.getCompanyPie()
        cache.set(pie_cache_key, pieData, 1800)
        cached_pie_data = pieData
    else:
        cached_pie_data = cached_pie
    if cached_people is None:
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
    return render(request, 'CompanyChar.html', {
        'userInfo': userInfo,
        'pieData': cached_pie_data,
        'companySizes': cached_people_data['companySizes'],
        'lineData': cached_people_data['lineData']
    })

