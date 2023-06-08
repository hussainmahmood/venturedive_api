from rest_framework.permissions import BasePermission
from .models import User

class IsLoggedIn(BasePermission):
	jargon = [User.UserGroup.ADMIN, User.UserGroup.SIMPLETON]
	def has_permission(self, request, view):
		if request.session.get('usergroup') in self.jargon:
			return True
		
		return False

class IsAdmin(IsLoggedIn):
	message = 'Not a Admin.'
	jargon = ['AD']

class IsSimpleton(IsLoggedIn):
	message = 'Not a SalesRep.'
	jargon = ['ST']