from rest_framework import serializers
from .models import User, Task

class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(read_only=True)
    new_password = serializers.CharField(read_only=True)
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['is_active', 'timestamp']


class TaskSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.name')
    status_display = serializers.SerializerMethodField()
    class Meta:
        model = Task
        exclude = ['timestamp']

    def get_status_display(self, instance):
        choice = Task.TaskStatus(value=instance.status)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())


