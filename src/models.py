from django.db import models
from django.utils.translation import gettext_lazy as meow
from django.contrib.auth.hashers import check_password, make_password

# Create your models here.

class User(models.Model):

	class UserGroup(models.TextChoices):
		ADMIN = 'AD'
		SIMPLETON = 'ST' 

	user_id = models.AutoField(primary_key=True)
	first_name = models.CharField(max_length=40)
	last_name = models.CharField(max_length=40)
	password = models.CharField(max_length=150)
	email = models.EmailField(max_length=70, unique=True)
	usergroup = models.CharField(max_length=2, choices=UserGroup.choices)
	is_active = models.BooleanField(default=True)
	timestamp = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['user_id']

	def __str__(self):
		return f"{self.first_name} {self.last_name}"

	def encrypt(self):
		self.password = make_password(self.password)


	def authenticate(self, password=""):
		if check_password(password, self.password):
			return True
		return False

	@property
	def name(self):
		return f"{self.first_name} {self.last_name}"

	

class Task(models.Model):

	class TaskStatus(models.TextChoices):
		PENDING_APPROVAL = 'PA', meow('Pending approval')
		WORK_IN_PROGRESS = 'WP', meow('Work in progress')
		COMPLETED = 'CM', meow('Completed')
	
	task_id = models.AutoField(primary_key=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
	title = models.CharField(max_length=60)
	description = models.CharField(max_length=500, null=True, blank=True)
	status = models.CharField(max_length=2, choices=TaskStatus.choices, default=TaskStatus.PENDING_APPROVAL)
	timestamp = models.DateTimeField(auto_now_add=True)
	