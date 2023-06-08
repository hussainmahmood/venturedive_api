from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from .permissions import (
    IsLoggedIn, IsAdmin, IsSimpleton
    )
from .models import User, Task

from .serializers import (
    UserSerializer, TaskSerializer
)

import smtplib

import pandas as pd


# Create your views here.

def set_session(request, user, remember_user=False):
    request.session['user'] = user.user_id
    request.session['usergroup'] = user.usergroup
    if remember_user:
        request.session.set_expiry(2592000)
    else:
        request.session.set_expiry(0)

def send_mail():
    sender = 'from@example.com'
    receivers = ['to@example.com']
    message = """From: From Person <from@example.com>
    To: To Person <to@example.com>
    Subject: SMTP email example


    This is a test message.
    """

    try:
        smtpObj = smtplib.SMTP('localhost')
        smtpObj.sendmail(sender, receivers, message)         
        print("Successfully sent email")
    except smtplib.SMTPException:
        pass

class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action in ['send_periodic_mail']:
            permission_classes = []
        elif self.action in ['login', 'signup']:
            permission_classes = []
        elif self.action in ['get_tasks', 'logout']:
            permission_classes = [IsLoggedIn]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = User.objects.all()
        return queryset
    
    @action(detail=False, methods=['post'])
    def signup(self, request):
        try:
            user = User.objects.create(**request.data)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        user.encrypt()
        user.save()
        return Response({'message': 'user created'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def login(self, request):
        email = request.data.get('email', '')
        password = request.data.get('password', '')
        try:
            user = self.get_queryset().get(email__iexact=email, is_active=True)
        except:
            return Response({'message': 'incorrect email or password'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            if not user.authenticate(password):
                return Response({'message': 'incorrect email or password'}, status=status.HTTP_400_BAD_REQUEST)

        set_session(request, user)
        return Response({'message': 'user logged in'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def logout(self, request):
        request.session.flush()
        return Response({"message": "successfully logged out"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def send_periodic_mail(self, request):
        pass

    
class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    
    def get_permissions(self):
        if self.action in ['get_all_tasks']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsLoggedIn]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = Task.objects.filter(user=self.request.session.get('user'))
        return queryset    
    
    def create(self,request):
        request.data['user_id'] = request.session.get('user')
        task = Task.objects.create(**request.data)
        return Response({"message": "successfully created"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def get_all_tasks(self, request):
        tasks = Task.objects.all()
        tasks =  self.paginate_queryset(tasks)
        serializer = TaskSerializer(tasks, many=True) 
        return self.get_paginated_response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        csv = request.FILES.get('csv')
        tasks_df = pd.read_csv(csv)
        tasks_df['task_id'].fillna(0, inplace=True)

        records = [
            {
                "task_id": Task.objects.filter(task_id=row.get("task_id")).latest('timestamp').task_id
                if Task.objects.filter(task_id=row.get("task_id")).exists()
                else None,
                "user_id": request.session.get('user'),
                **row,
            }
            for _, row in tasks_df.iterrows()
        ]

        records_to_update = []
        records_to_create = []

        [
            records_to_update.append(record)
            if record["task_id"] != 0
            else records_to_create.append(record)
            for record in records
        ]

        [record.pop("task_id") for record in records_to_create]

        created_records = Task.objects.bulk_create(
            [Task(**record) for record in records_to_create], batch_size=100)

        updated_records = Task.objects.bulk_update(
            [
                Task(**record)
                for record in records_to_update
            ],
            ['title', 'description'],
            batch_size=100
        )

        return Response({"message": "successfully uploaded"}, status=status.HTTP_200_OK)