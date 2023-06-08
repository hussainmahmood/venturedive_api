from django.core import signing
from rest import settings
from rest_framework.permissions import BasePermission, IsAuthenticated
from .models import User

class IsLoggedIn(BasePermission):
	jargon = ['AD', 'DA', 'TA', 'OM', 'OT', 'SR', 'VN']
	def has_permission(self, request, view):
		session_secret = request.query_params.get('session', "")
		try:
			session = signing.loads(session_secret, salt=settings.ROOT_SECRET)
		except:
			return False
		try:
			user = User.objects.get(user_id=int(session.get('user_id', -1)))
		except:
			return False
		else:
			if user.usergroup in self.jargon:
				return True
			else:
				return False

class IsAdmin(IsLoggedIn):
	message = 'Not a Admin.'
	jargon = ['AD']

class IsDeliveryAdmin(IsLoggedIn):
	message = 'Not a Delivery Admin.'
	jargon = ['DA']

class IsTitleAdmin(IsLoggedIn):
	message = 'Not a Title Admin.'
	jargon = ['TA']

class IsOperationsManager(IsLoggedIn):
	message = 'Not a Operations Manager.'
	jargon = ['OM']

class IsOperationsTeam(IsLoggedIn):
	message = 'Not a Operations Team.'
	jargon = ['OT']
	
class IsSalesRep(IsLoggedIn):
	message = 'Not a SalesRep.'
	jargon = ['SR']

class IsVendor(IsLoggedIn):
	message = 'Not a Vendor.'
	jargon = ['VN']