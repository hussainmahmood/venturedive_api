from rest_framework import routers
from .views import (
    UserViewSet, ModeOfPaymentViewSet, WarrantyViewSet, InsuranceViewSet, 
    CarViewSet, SalesViewSet, TaskViewSet
)

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'mode_of_payment', ModeOfPaymentViewSet, basename='mode_of_payment')
router.register(r'warranty', WarrantyViewSet, basename='warranty')
router.register(r'insurance', InsuranceViewSet, basename='insurance')
router.register(r'cars', CarViewSet, basename='cars')
router.register(r'sales', SalesViewSet, basename='sales')
router.register(r'tasks', TaskViewSet, basename='tasks')
