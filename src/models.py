import os
from django.contrib import admin
from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.contrib.postgres.fields import ArrayField
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as meow
from django.contrib.auth.hashers import check_password, make_password
from datetime import datetime, timedelta


@deconstructible
class path_and_rename(object):
    def __init__(self, path):
    	self.path = path

    def __call__(self, instance, filename):
    	if self.path == "img/cars/":
    		sub_dir = f'{self.path}{instance.car.car_id}/'
    	elif self.path == "img/tasks/":
    		sub_dir = f'{self.path}{instance.car.car_id}/'
    	elif self.path == "img/tasks_complete/":
    		sub_dir = f'{self.path}{instance.car.car_id}/'
    	elif self.path == "icons/":
    		sub_dir = f'{self.path}'

    	return os.path.join(sub_dir, filename)

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

	def __init__(self, *args, **kwargs):
	    super(User, self).__init__(*args, **kwargs)
	    self.initial_password = self.password

	# def save(self, *args, **kwargs):
	#     if not (check_password(self.password, self.initial_password) or self.password == self.initial_password) or self._state.adding:
	#         self.password = make_password(self.password)
	#     else:
	#         self.password = self.initial_password
	#     super(User, self).save(*args, **kwargs)

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
	