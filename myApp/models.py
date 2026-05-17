from django.db import models
import uuid
from django.utils import timezone


class Job(models.Model):
    href = models.CharField('详情页', max_length=500, default='', primary_key=True)
    name = models.CharField('职位', max_length=255, default='')
    salaryMin = models.DecimalField('薪资下限', max_digits=10, decimal_places=2, default=0.00)
    salaryMax = models.DecimalField('薪资上限', max_digits=10, decimal_places=2, default=0.00)
    salaryBonus = models.IntegerField('年终奖', default=0)
    city = models.CharField('城市', max_length=255, default='', db_column='location')
    exp = models.CharField('经验', max_length=255, default='', db_column='experience')
    edu = models.CharField('学历', max_length=255, default='', db_column='education')
    jobType = models.CharField('职位类型', max_length=255, default='')
    num = models.IntegerField('招聘人数', default='')
    tags = models.CharField('标签', max_length=255, default='', db_column='tagList')
    content = models.TextField('职位描述', default='')
    com = models.CharField('公司', max_length=255, default='', db_column='company')
    comSize = models.CharField('公司规模', max_length=255, default='', db_column='companySize')
    comTag = models.CharField('公司类型', max_length=255, default='', db_column='companyTag')
    staff = models.CharField('经理', max_length=255, default='')
    keyList = models.TextField('关键词', default='')
    delete = models.IntegerField('是否删除', default=0, db_column='deleteStatus')

    class Meta:
        db_table = 'job'


def avatar_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    unique_name = f"avatar_{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
    return f"avatar/{unique_name}"


def resume_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    unique_name = f"resume_{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
    return f"resume/{unique_name}"


class Joblist(models.Model):
    id = models.AutoField('id', primary_key=True)
    name = models.CharField('职位名称', max_length=255, default='')
    salaryMin = models.DecimalField('薪资下限', max_digits=10, decimal_places=2, default=0.00)
    salaryMax = models.DecimalField('薪资上限', max_digits=10, decimal_places=2, default=0.00)
    salaryBonus = models.IntegerField('年终奖', default=0)
    city = models.CharField('城市', max_length=255, default='', db_column='location')
    exp = models.CharField('经验', max_length=255, default='', db_column='experience')
    edu = models.CharField('学历', max_length=255, default='', db_column='education')
    industry = models.CharField('行业', max_length=255, default='')
    num = models.IntegerField('招聘人数', default=0)
    tags = models.CharField('福利待遇', max_length=255, default='', db_column='tagList')
    type = models.CharField('职位类型', max_length=255, default='')
    content = models.TextField('职位描述', default='')
    company = models.IntegerField('公司', default='')
    staff = models.IntegerField('经理', default='')
    time = models.DateTimeField('发布时间', auto_now_add=True)
    keyList = models.TextField('关键词', default='')
    urgency = models.CharField('紧急程度', max_length=255, default='')
    status = models.CharField('状态', max_length=255, default='')
    delete = models.IntegerField('是否删除', default=0)

    class Meta:
        db_table = 'joblist'


# 求职者表
class User(models.Model):
    id = models.AutoField('id', primary_key=True)
    username = models.CharField('用户名', max_length=255, default='')
    password = models.CharField('密码', max_length=255, default='')
    realName = models.CharField('真实姓名', max_length=255, default='')
    sex = models.CharField('性别', max_length=255, default='')
    age = models.IntegerField('年龄', default=0)
    mobile = models.CharField('手机号', max_length=255, default='')
    email = models.CharField('邮箱', max_length=255, default='')
    edu = models.CharField('学历', max_length=255, default='', db_column='education')
    exp = models.CharField('工作经验', max_length=255, default='', db_column='experience')
    city = models.CharField('意向城市', max_length=255, default='')
    work = models.CharField('意向岗位', max_length=255, default='')
    resume = models.FileField('简历', upload_to=resume_upload_path, default='')
    avatar = models.FileField('用户图像', upload_to=avatar_upload_path, default='avatar/cat.jpg')
    lastLoginTime = models.DateTimeField('上次登录时间', null=True, blank=True)
    isOnline = models.BooleanField('是否在线', default=False)
    createTime = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'user'


# 招聘者表
class Employer(models.Model):
    id = models.AutoField('id', primary_key=True)
    username = models.CharField('用户名', max_length=255, default='')
    password = models.CharField('密码', max_length=255, default='')
    realName = models.CharField('真实姓名', max_length=255, default='')
    sex = models.CharField('性别', max_length=255, default='')
    position = models.CharField('职位', max_length=255, default='')
    company = models.IntegerField('所属公司', default='')
    comName = models.CharField('公司名称', max_length=255, default='')
    avatar = models.FileField('用户图像', upload_to=avatar_upload_path, default='avatar/cat.jpg')
    lastLoginTime = models.DateTimeField('上次登录时间', null=True, blank=True)
    isOnline = models.BooleanField('是否在线', default=False)
    createTime = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'employer'


def certification_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    unique_name = f"certification_{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
    return f"certifications/{unique_name}"


class Company(models.Model):
    id = models.AutoField('id', primary_key=True)
    name = models.CharField('公司名称', max_length=255, default='')
    size = models.CharField('公司规模', max_length=255, default='')
    tag = models.CharField('公司所属行业', max_length=255, default='')
    location = models.CharField('公司详细地址', max_length=255, default='')
    city = models.CharField('公司所在地', max_length=255, default='')
    logo = models.FileField('公司logo', upload_to=avatar_upload_path, default='avatar/cat.jpg')
    content = models.TextField('公司简介', default='')
    verification = models.FileField('公司认证信息', upload_to=certification_upload_path, default='')
    vfstatus = models.IntegerField('是否审核', default=0)
    vfbool = models.IntegerField('是否通过认证', default=0)

    class Meta:
        db_table = 'company'


class History(models.Model):
    id = models.AutoField('id', primary_key=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    count = models.IntegerField('点击次数', default=1)
    duration = models.TimeField('时长', default='00:00:00')

    class Meta:
        db_table = 'history'


class Industry(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="行业代码")
    name = models.CharField(max_length=100, verbose_name="行业名称")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级行业"
    )
    level = models.IntegerField(default=0, verbose_name="层级")

    class Meta:
        verbose_name = "行业分类"
        verbose_name_plural = "行业分类"
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)
