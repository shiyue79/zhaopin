# myapp/serializers.py
from rest_framework import serializers
from .models import User, Joblist, Company, Industry


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


#
#
# class ApplicationSerializer(serializers.ModelSerializer):
#     job = JobSerializer(read_only=True)
#     user = UserSerializer(read_only=True)
#
#     class Meta:
#         model = Application
#         fields = '__all__'
#         read_only_fields = ['applied_at', 'status']


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
    """匹配分析序列化器"""
    candidate_id = serializers.IntegerField()
    match_score = serializers.FloatField()
    strengths = serializers.ListField(child=serializers.CharField())
    weaknesses = serializers.ListField(child=serializers.CharField())
    suggestions = serializers.ListField(child=serializers.CharField())
