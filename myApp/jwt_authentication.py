# myApp/jwt_authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import User, Employer

class CustomJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        try:
            user_id = validated_token['user_id']
            account = validated_token.get('account', 'user')

            if account == 'admin':
                return Employer.objects.get(pk=user_id)
            else:
                return User.objects.get(pk=user_id)
        except (KeyError, User.DoesNotExist, Employer.DoesNotExist):
            return None
