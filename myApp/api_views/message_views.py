import uuid
from django.db.models import Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from ..models import Message, User, Employer
from ..serializers import MessageSerializer
from django.utils import timezone


class MessageViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='conversations')
    def get_conversations(self, request):
        try:
            username = request.session.get('username')
            account = request.session.get('account')
            if not username:
                return JsonResponse({'code': 401, 'msg': '未登录', 'data': None}, status=401)
            if account == 'user':
                user = User.objects.get(username=username)
            else:
                user = Employer.objects.get(username=username)
            is_employer = (account == 'admin')
            if is_employer:
                messages = Message.objects.filter(employer_id=user.id).select_related('user', 'employer').order_by(
                    'createTime')
            else:
                messages = Message.objects.filter(user_id=user.id).select_related('user', 'employer').order_by(
                    'createTime')

            conversations = {}
            for msg in messages:
                sender = msg.get_sender()
                receiver = msg.get_receiver()
                if not sender or not receiver:
                    continue
                # 确定对方用户
                if sender.id == user.id:
                    other = receiver
                else:
                    other = sender
                if isinstance(other, User):
                    other_type = 'user'
                    other_account = 'user'
                else:
                    other_type = 'admin'
                    other_account = 'admin'
                conv_key = f"{other_type}_{other.id}"
                if conv_key not in conversations:
                    conversations[conv_key] = {
                        'messages': [],
                        'unread_count': 0,
                        'other': other,
                        'other_type': other_type,
                        'other_account': other_account
                    }
                conversations[conv_key]['messages'].append(msg)

                if msg.get_receiver().id == user.id and msg.isRead == 0:
                    conversations[conv_key]['unread_count'] += 1

            result_list = []
            for conv_key, data in conversations.items():
                other = data['other']
                last_msg_obj = data['messages'][-1]
                last_msg_data = MessageSerializer(last_msg_obj).data
                result_list.append({
                    'user': {
                        'id': other.id,
                        'account': data['other_account'],
                        'username': other.username,
                        'realname': other.realName,
                        'avatar': other.avatar.url if other.avatar else None,
                        'online': getattr(other, 'isOnline', False)
                    },
                    'last_message': last_msg_data,
                    'unread_count': data['unread_count']
                })

            return JsonResponse({'code': 200, 'msg': '成功', 'data': result_list})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e), 'data': None}, status=500)

    @action(detail=False, methods=['get'], url_path='messages')
    def get_messages(self, request):
        try:
            username = request.session.get('username')
            account = request.session.get('account')
            if not username:
                return JsonResponse({'code': 401, 'msg': '未登录', 'data': None}, status=401)
            if account == 'user':
                user = User.objects.get(username=username)
            else:
                user = Employer.objects.get(username=username)
            other_username = request.query_params.get('userId')
            other_user_type = request.query_params.get('userType', 'user')
            if not other_username:
                return JsonResponse({'code': 400, 'msg': '缺少 userId', 'data': None}, status=400)
            is_employer = (account == 'admin')
            other_is_employer = (other_user_type == 'admin')
            if is_employer and not other_is_employer:
                messages = Message.objects.filter(
                    employer_id=user.id,
                    user_id=other_username
                ).select_related('user', 'employer').order_by('createTime')
            elif not is_employer and other_is_employer:
                messages = Message.objects.filter(
                    user_id=user.id,
                    employer_id=other_username
                ).select_related('user', 'employer').order_by('createTime')
            else:
                messages = Message.objects.none()
            serializer = MessageSerializer(messages, many=True)
            return JsonResponse({'code': 200, 'msg': '成功', 'data': serializer.data})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e), 'data': None}, status=500)

    @action(detail=False, methods=['post'], url_path='send')
    def send_message(self, request):
        try:
            username = request.session.get('username')
            account = request.session.get('account')
            if not username:
                return JsonResponse({'code': 401, 'msg': '未登录', 'data': None}, status=401)
            if account == 'user':
                user = User.objects.get(username=username)
            else:
                user = Employer.objects.get(username=username)
            receiver_id = request.data.get('receiver')
            content = request.data.get('content')
            msg_type = request.data.get('type', 'text')
            file_url = request.data.get('file_url', '')
            if not receiver_id or not content:
                return JsonResponse({'code': 400, 'msg': '参数缺失', 'data': None}, status=400)
            is_employer = (account == 'admin')
            msg_data = {
                'uuid': str(uuid.uuid4()),
                'content': content,
                'type': msg_type,
                'fileUrl': file_url,
                'createTime': timezone.now(),
                'isRead': 0
            }
            if is_employer:
                msg_data['employer_id'] = user.id
                msg_data['user_id'] = receiver_id
                msg_data['senderType'] = 2
            else:
                msg_data['user_id'] = user.id
                msg_data['employer_id'] = receiver_id
                msg_data['senderType'] = 1
            msg = Message.objects.create(**msg_data)
            return JsonResponse({'code': 200, 'msg': '发送成功', 'data': MessageSerializer(msg).data})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e), 'data': None}, status=500)

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        try:
            username = request.session.get('username')
            account = request.session.get('account')
            if not username:
                return JsonResponse({'code': 401, 'msg': '未登录', 'data': None}, status=401)
            if account == 'user':
                user = User.objects.get(username=username)
            else:
                user = Employer.objects.get(username=username)
            sender_id = request.data.get('senderId')
            sender_type = request.data.get('senderType', 'user')
            if not sender_id:
                return JsonResponse({'code': 400, 'msg': '参数缺失', 'data': None}, status=400)
            is_employer = (account == 'admin')
            sender_is_employer = (sender_type == 'admin')
            filter_kwargs = {'isRead': 0}
            if is_employer and not sender_is_employer:
                filter_kwargs['employer_id'] = user.id
                filter_kwargs['user_id'] = sender_id
                filter_kwargs['senderType'] = 1
            elif not is_employer and sender_is_employer:
                filter_kwargs['user_id'] = user.id
                filter_kwargs['employer_id'] = sender_id
                filter_kwargs['senderType'] = 2
            updated_count = Message.objects.filter(**filter_kwargs).update(isRead=1)
            return JsonResponse({'code': 200, 'msg': '成功', 'data': {'updated_count': updated_count}})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e), 'data': None}, status=500)
