# myapp/serializers.py
from rest_framework import serializers
from .models import User, Joblist, Company, Industry, Application, InterviewStage, Message


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class TalentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'realName', 'sex', 'age',
            'mobile', 'email', 'edu', 'exp', 'city', 'work',
            'avatar', 'resume', 'lastLoginTime', 'isOnline'
        ]


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Joblist
        fields = '__all__'


class ApplicationSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ['applied_at', 'status']


class InterviewStageSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = InterviewStage
        fields = ['id', 'stage', 'stage_display', 'time', 'data', 'comment', 'passed', 'createTime']
        read_only_fields = ['id', 'createTime']


class ApplicationListSerializer(serializers.ModelSerializer):
    """用于列表展示的简化序列化器"""
    applicant_name = serializers.SerializerMethodField()
    applicant_phone = serializers.SerializerMethodField()
    applicant_email = serializers.SerializerMethodField()
    position_name = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    education = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    interview_stages = serializers.SerializerMethodField()
    current_stage_index = serializers.SerializerMethodField()
    resume_url = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'applicant_name', 'applicant_phone', 'applicant_email',
            'position_name', 'experience', 'education', 'city',
            'status', 'applyTime', 'tags_list', 'interview_stages',
            'current_stage_index', 'resume_url', 'feedback'
        ]
        read_only_fields = fields

    def get_applicant_name(self, obj):
        try:
            # 优先返回真实姓名，如果没有则返回用户名
            if obj.user.realName:
                return obj.user.realName
            return obj.user.username
        except (AttributeError, User.DoesNotExist):
            return '未知'

    def get_applicant_phone(self, obj):
        try:
            return obj.user.mobile or None
        except AttributeError:
            return None

    def get_applicant_email(self, obj):
        try:
            return obj.user.email or None
        except AttributeError:
            return None

    def get_position_name(self, obj):
        try:
            return obj.job.name
        except (AttributeError, Joblist.DoesNotExist):
            return '未知岗位'

    def get_experience(self, obj):
        try:
            return obj.user.exp or None
        except AttributeError:
            return None

    def get_education(self, obj):
        try:
            return obj.user.edu or None
        except AttributeError:
            return None

    def get_city(self, obj):
        try:
            return obj.user.city or None
        except AttributeError:
            return None

    def get_tags_list(self, obj):
        if obj.tags:
            return [tag.strip() for tag in obj.tags.split(',') if tag.strip()]
        return []

    def get_interview_stages(self, obj):
        stages = InterviewStage.objects.filter(application=obj.id).order_by('createTime')
        return InterviewStageSerializer(stages, many=True).data

    def get_current_stage_index(self, obj):
        stages = InterviewStage.objects.filter(application=obj.id).order_by('createTime')
        if not stages.exists():
            return -1
        return stages.count() - 1

    def get_resume_url(self, obj):
        try:
            if obj.user.resume:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.user.resume.url)
                return obj.user.resume.url
            return None
        except AttributeError:
            return None


class ApplicationDetailSerializer(serializers.ModelSerializer):
    """用于详情的完整序列化器"""
    applicant_info = serializers.SerializerMethodField()
    job_info = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()
    interview_stages = InterviewStageSerializer(source='stages', many=True, read_only=True)

    class Meta:
        model = Application
        fields = '__all__'

    def get_applicant_info(self, obj):
        try:
            user = obj.user
            return {
                'id': user.id,
                'username': user.username,
                'realName': user.realName,
                'mobile': user.mobile,
                'email': user.email,
                'edu': user.edu,
                'exp': user.exp,
                'city': user.city,
                'resume': user.resume.url if user.resume else None
            }
        except AttributeError:
            return None

    def get_job_info(self, obj):
        try:
            job = obj.job
            return {
                'id': job.id,
                'name': job.name,
                'company': job.company
            }
        except AttributeError:
            return None

    def get_tags_list(self, obj):
        if obj.tags:
            return [tag.strip() for tag in obj.tags.split(',') if tag.strip()]
        return []


class IndustrySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Industry
        fields = ['code', 'name', 'children']

    def get_children(self, obj):
        children = obj.children.all()
        if children.exists():
            return IndustrySerializer(children, many=True).data
        return []


class MatchAnalysisSerializer(serializers.Serializer):
    candidate_id = serializers.IntegerField()
    match_score = serializers.FloatField()
    strengths = serializers.ListField(child=serializers.CharField())
    weaknesses = serializers.ListField(child=serializers.CharField())
    suggestions = serializers.ListField(child=serializers.CharField())

class MessageSerializer(serializers.ModelSerializer):
    # 字段映射
    sender = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()
    receiver_type = serializers.SerializerMethodField()
    file_url = serializers.CharField(source='fileUrl')
    create_time = serializers.DateTimeField(source='createTime')
    is_read = serializers.IntegerField(source='isRead')
    
    # 补充发送者和接收者的详细信息
    sender_info = serializers.SerializerMethodField()
    receiver_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'uuid', 'sender', 'sender_type', 'receiver', 'receiver_type', 
                  'content', 'type', 'file_url', 'create_time', 'is_read', 'sender_info', 'receiver_info']
        read_only_fields = fields

    def get_sender(self, obj):
        sender = obj.get_sender()
        return sender.id if sender else None

    def get_sender_type(self, obj):
        return obj.get_sender_type_str()

    def get_receiver(self, obj):
        receiver = obj.get_receiver()
        return receiver.id if receiver else None

    def get_receiver_type(self, obj):
        return obj.get_receiver_type_str()

    def get_sender_info(self, obj):
        sender = obj.get_sender()
        if not sender:
            return None
        return {
            'id': sender.id,
            'username': sender.username,
            'avatar': sender.avatar.url if sender.avatar else None,
            'online': getattr(sender, 'isOnline', False)
        }

    def get_receiver_info(self, obj):
        receiver = obj.get_receiver()
        if not receiver:
            return None
        return {
            'id': receiver.id,
            'username': receiver.username,
            'avatar': receiver.avatar.url if receiver.avatar else None,
            'online': getattr(receiver, 'isOnline', False)
        }
