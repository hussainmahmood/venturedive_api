import base64, time, re
from rest import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, F, Sum
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from .permissions import (
    IsLoggedIn, IsAdmin, IsDeliveryAdmin, IsTitleAdmin, IsSalesRep, 
    IsOperationsManager, IsOperationsTeam, IsVendor
    )
from datetime import datetime, timedelta
from multiprocessing import Process

from .models import User, ModeOfPayment, Warranty, Insurance, Car, CarImage, Sales, Payment, Task

from .serializers import (
    UserDisplaySerializer, UserSerializer, ValueLabelDisplaySerializer, ModeOfPaymentSerializer, 
    WarrantySerializer, InsuranceSerializer, CarSerializer, InspectedCarSerializer, 
    CarImageSerializer, SalesSerializer, PaymentSerializer, TotalPaymentSerializer, TradeInSerializer, TaskSerializer, LoginSerializer, 
    SalesPerformanceSerializer, CommissionPayableSerializer
)

from .scrapper import get_cars
from .ftp_import import update_cars_data




# Create your views here.

# def set_session(request, user, remember_user=False):
#     request.session['user'] = user.user_id
#     request.session['company'] = user.company.company_id
#     request.session['usergroup'] = user.user_group.user_group_id
#     if remember_user:
#         request.session.set_expiry(2592000)
#     else:
#         request.session.set_expiry(0)

from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer

# @api_view(('GET',))
# @renderer_classes((JSONRenderer,))
# def image_display(request, car_id, image_name):
#     car = Car.objects.get(car_id=car_id)
#     serializer = CarImageSerializer(car.images.all(), many=True, context={'request': request})
#     return Response(serializer.data, status=status.HTTP_200_OK)

def get_user_from_session(request):
    session_secret = request.query_params.get('session', "")
    try:
        session = signing.loads(session_secret, salt=settings.ROOT_SECRET)
    except:
        return None
    return session.get('user_id', None)

def get_usergroup_from_session(request):
    session_secret = request.query_params.get('session', "")
    try:
        session = signing.loads(session_secret, salt=settings.ROOT_SECRET)
    except:
        return None
    return session.get('usergroup', None)

class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'login':
            permission_classes = []
        elif self.action == 'logout' or self.action == 'select' or self.action == 'set_password':
            permission_classes = [IsLoggedIn]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = User.objects.all()
        search = self.request.query_params.get('search')
        usergroup = self.request.query_params.get('usergroup')
        if search is not None:
            queryset = queryset.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search) | Q(ssn__icontains=search))
        if usergroup is not None:
            queryset = queryset.filter(usergroup=usergroup)
        return queryset

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username', '') # ums/faique
        password = request.data.get('password', '')
        try:
            user = self.get_queryset().get(Q(username__iexact=username) | Q(email__iexact=username), active_status=True)
        except:
            return Response({'error': 'Incorrect username or password.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            if not user.authenticate(password):
                return Response({'error': 'Incorrect username or password.'}, status=status.HTTP_400_BAD_REQUEST)

        session_obj = {"user_id": user.user_id, "usergroup": user.usergroup}
        session_secret = signing.dumps(session_obj, salt=settings.ROOT_SECRET)
        serializer = LoginSerializer({"session": session_secret, "usergroup": user.get_usergroup_display(), "name": user.name, "usergroup_display": ' '.join(word.capitalize() for word in User.UserGroup(value=user.usergroup).name.replace("_", " ").split())})
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def logout(self, request):
        return Response({"message!": "Successfully logout!"})

    def list(self, request):
        results = self.paginate_queryset(self.get_queryset())
        serializer = UserDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    def retrieve(self, request, pk=None):
        user = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = UserDisplaySerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def select(self, request):
        users = [{'value': user.user_id, 'label': ' '.join([user.first_name.capitalize(), user.last_name.capitalize()])} for user in self.get_queryset()]
        results = self.paginate_queryset(users)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def set_password(self, request):
        password = request.data.get('password', '')
        new_password = request.data.get('new_password', '')

        session_secret = request.query_params.get('session', "")
        try:
            session = signing.loads(session_secret, salt=settings.ROOT_SECRET)
        except:
            session = {}
        try:
            user = self.get_queryset().get(user_id=int(session.get('user_id', -1)))
        except:
            user = None

        if user.authenticate(password):
            user.password = new_password
            user.save()
            return Response({'status': 'password set'})
        else:
            return Response({'error': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def get_roles(self, request):
        roles = [{'value': usergroup.value, 'label': ' '.join(word.capitalize() for word in usergroup.name.replace("_", " ").split())} for usergroup in User.UserGroup]
        results = self.paginate_queryset(roles)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def pay_commission(self, request):
        seller = request.data.get('seller', None)
        if seller is None:
            return Response({'error': 'seller not selected.'}, status=status.HTTP_400_BAD_REQUEST)
        timestamp = request.data.get('timestamp')
        timestamp = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f')
        try:
            user = self.get_queryset().get(user_id=seller, usergroup=User.UserGroup.SALES_REPRESENTATIVE)
        except:
            return Response({'error': 'seller not found.'}, status=status.HTTP_400_BAD_REQUEST)

        user.sales.filter(status=Sales.SalesStatus.FUNDED, commission_paid=False, funded_timestamp__lte=timestamp).update(commission_paid=True, commission_paid_timestamp=datetime.now())
        return Response({'status': 'commission paid'})

    @action(detail=False, methods=['get'])
    def sales_performance(self, request):
        date = request.query_params.get('date', "")
        date_pattern = re.compile("^\d{4}-\d{2}-\d{2}$")
        if re.match(date_pattern, date):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        else:
            date = datetime.now().date()
        queryset = [{'name':seller.name, 
                     'sales_count':seller.sales_count(date),
                     'insurance_count': seller.insurance_count(date), 
                     'warranty_count': seller.warranty_count(date)} for seller in self.get_queryset().filter(usergroup=User.UserGroup.SALES_REPRESENTATIVE)]
        results = self.paginate_queryset(queryset)
        serializer = SalesPerformanceSerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def commission_payable(self, request):
        seller = request.query_params.get('seller', None)
        unpaid_commission = {'commission_payable': 0.00, 'timestamp': datetime.now()}
        
        if seller is not None:
            try:
                user = self.get_queryset().get(user_id=seller, usergroup=User.UserGroup.SALES_REPRESENTATIVE)
            except:
                return Response({'error': 'seller not found.'}, status=status.HTTP_400_BAD_REQUEST)

            unpaid_sales = user.sales.filter(status=Sales.SalesStatus.FUNDED, commission_paid=False)
        else:
            unpaid_sales = Sales.objects.filter(status=Sales.SalesStatus.FUNDED, commission_paid=False)
        
        if unpaid_sales.exists():
            unpaid_commission['commission_payable'] = unpaid_sales.aggregate(commission_payable=Sum('commission'))['commission_payable']
        
        return Response(unpaid_commission)

    @action(detail=False, methods=['get'])
    def commission_paid(self, request):
        seller = request.query_params.get('seller', None)
        paid_commission = {'commission_paid': 0.00}
        start = request.query_params.get('start_date', "")
        end = request.query_params.get('end_date', "")
        date_pattern = re.compile("^\d{4}-\d{2}-\d{2}$")
        if seller is not None:
            try:
                user = self.get_queryset().get(user_id=seller, usergroup=User.UserGroup.SALES_REPRESENTATIVE)
            except:
                return Response({'error': 'seller not found.'}, status=status.HTTP_400_BAD_REQUEST)

            paid_sales = user.sales.filter(status=Sales.SalesStatus.FUNDED, commission_paid=True)
        else:
            paid_sales = Sales.objects.filter(status=Sales.SalesStatus.FUNDED, commission_paid=True)
        
        if re.match(date_pattern, start):
            start = datetime.strptime(start, '%Y-%m-%d').date()
            paid_sales = paid_sales.filter(commission_paid_timestamp__gte=start)
        if re.match(date_pattern, end):
            end = datetime.strptime(end, '%Y-%m-%d').date()
            paid_sales = paid_sales.filter(commission_paid_timestamp__lte=end)
        
        if paid_sales.exists():
            paid_commission = paid_sales.aggregate(commission_paid=Sum('commission'))
        
        return Response(paid_commission)


class ModeOfPaymentViewSet(ModelViewSet):
    serializer_class = ModeOfPaymentSerializer

    def get_permissions(self):
        if self.action == 'retrieve' or self.action == 'list' or self.action == 'get_modes':
            permission_classes = [IsAdmin|IsSalesRep]
        elif self.action == 'add_mode':
            permission_classes = [IsSalesRep]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return ModeOfPayment.objects.all()

    @action(detail=False, methods=['post'])
    def add_mode(self, request):
        data = {}
        data["name"] = self.request.data.get("name")
        data["automatic_addition"] = True
        serializer = ModeOfPaymentSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=False, methods=['get'])
    def get_modes(self, request):
        modes = [{'value': mode.mopay_id, 'label': mode.name} for mode in self.get_queryset()]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)


class WarrantyViewSet(ModelViewSet):
    serializer_class = WarrantySerializer

    def get_permissions(self):
        if self.action == 'retrieve' or self.action == 'list' or self.action == 'get_modes':
            permission_classes = [IsAdmin|IsSalesRep]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Warranty.objects.all()

    @action(detail=False, methods=['get'])
    def get_modes(self, request):
        modes = [{'value': mode.warranty_id, 'label': mode.label} for mode in self.get_queryset()]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

class InsuranceViewSet(ModelViewSet):
    serializer_class = InsuranceSerializer

    def get_permissions(self):
        if self.action == 'retrieve' or self.action == 'list' or self.action == 'get_modes':
            permission_classes = [IsAdmin|IsSalesRep]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Insurance.objects.all()

    @action(detail=False, methods=['get'])
    def get_modes(self, request):
        modes = [{'value': mode.insurance_id, 'label': mode.label} for mode in self.get_queryset()]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

class CarViewSet(ModelViewSet):
    serializer_class = CarSerializer

    def get_queryset(self):
        queryset = Car.objects.prefetch_related('images')
        search = self.request.query_params.get('search')
        status = self.request.query_params.get('status')
        inspection_recommendation = self.request.query_params.get('inspection_recommendation')
        if search is not None:
            queryset = queryset.filter(Q(vin__icontains=search) | Q(make__icontains=search) | Q(model__icontains=search) | Q(year__icontains=search))
        if status is not None:
            queryset = queryset.filter(status=status)
        if inspection_recommendation is not None:
            queryset = queryset.filter(inspection_recommendation=inspection_recommendation)

        return queryset

    def bulk_update(self, request):
        pass

    @action(detail=False, methods=['get'])
    def get_inspected(self, request):
        results = self.paginate_queryset(self.get_queryset().filter(status=Car.CarStatus.AT_LOT, inspection_recommendation=Car.InspectionRecommendation.SELL, inspected=True))
        serializer = InspectedCarSerializer(results, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_uninspected(self, request):
        results = self.paginate_queryset(self.get_queryset().filter(status=Car.CarStatus.AT_LOT, inspected=False))
        serializer = CarSerializer(results, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def send_to_auction(self, request):
        try:
            car = self.get_queryset().get(car_id=request.data.get('car_id'))
        except:
            return Response({'error': 'car not found.'}, status=status.HTTP_400_BAD_REQUEST)

        car.inspection_recommendation = Car.InspectionRecommendation.SEND_TO_AUCTION
        car.save()
        return Response({'status': 'recommendation updated.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def import_data(self, request):
        try:
            update_cars_data()
        except Exception as e:
            return Response({'datetime': datetime.now(), 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'datetime': datetime.now(), 'status': 'updated.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def get_status(self, request):
        modes = [{'value': mode.value, 'label': ' '.join(word.capitalize() for word in mode.name.replace("_", " ").split())} for mode in Car.CarStatus]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_mop(self, request):
        modes = [{'value': mode.value, 'label': ' '.join(word.capitalize() for word in mode.name.replace("_", " ").split())} for mode in Car.ModeOfPurchase]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_inspection_recommendation(self, request):
        modes = [{'value': mode.value, 'label': ' '.join(word.capitalize() for word in mode.name.replace("_", " ").split())} for mode in Car.InspectionRecommendation]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def delete_inspection_tasks(self, request):
        car_id = request.data.get('car_id')
        try:
            car = self.get_queryset().get(car_id=car_id, status=Car.CarStatus.AT_LOT, inspected=False)
        except:
            return Response({'error': 'no car found.'}, status=status.HTTP_400_BAD_REQUEST)

        car.tasks.filter(task_type=Task.TaskType.INSPECTION_TASK).delete()
        return Response({'status': 'all tasks deleted.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def complete_inspection(self, request):
        car_id = request.data.get('car_id')
        try:
            car = self.get_queryset().get(car_id=car_id, status=Car.CarStatus.AT_LOT, inspected=False)
        except:
            return Response({'error': 'no car found.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            car.inspected = True
            car.save()
        
        return Response({'status': 'inspection complete.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def complete_state_inspection(self, request):
        car_id = request.data.get('car_id')
        try:
            car = self.get_queryset().get(car_id=car_id, status=Car.CarStatus.AT_LOT, inspected=False)
        except:
            return Response({'error': 'no car found.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            car.state_inspected = True
            car.save()
        
        return Response({'status': 'state inspection complete.'}, status=status.HTTP_200_OK)


class SalesViewSet(ModelViewSet):
    queryset = Sales.objects.all()
    serializer_class = SalesSerializer

    def get_permissions(self):
        if self.action == 'retrieve' or self.action == 'list':
            permission_classes = [IsAdmin|IsSalesRep|IsDeliveryAdmin|IsTitleAdmin]
        elif self.action == 'commission_paid' or self.action == 'commission_unpaid':
            permission_classes = [IsAdmin]
        elif self.action == 'title_sales':
            permission_classes = [IsAdmin|IsTitleAdmin]
        elif self.action == 'deliver_sales':
            permission_classes = [IsAdmin|IsDeliveryAdmin]
        else:
            permission_classes = [IsSalesRep]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sales.objects.all()
        requested_by = get_user_from_session(self.request)
        usergroup = get_usergroup_from_session(self.request)
        if usergroup == User.UserGroup.SALES_REPRESENTATIVE:
            queryset = queryset.filter(seller=requested_by)
        unfunded = self.request.query_params.get('unfunded')
        untitled = self.request.query_params.get('untitled')
        undelivered = self.request.query_params.get('undelivered')
        if unfunded is not None:
            if unfunded == '1':
                queryset = queryset.filter(status=Sales.SalesStatus.SOLD)
            elif unfunded == '0':
                queryset = queryset.filter(status=Sales.SalesStatus.FUNDED)
        if untitled is not None:
            if untitled == '1':
                queryset = queryset.filter(status=Sales.SalesStatus.FUNDED, is_titled=False)
            elif untitled == '0':
                queryset = queryset.filter(status=Sales.SalesStatus.FUNDED, is_titled=True)
        if undelivered is not None:
            if undelivered == '1':
                queryset = queryset.filter(status=Sales.SalesStatus.FUNDED, is_delivered=False)
            elif undelivered == '0':
                queryset = queryset.filter(status=Sales.SalesStatus.FUNDED, is_delivered=True)
        return queryset


    def create(self, request):
        try:
            trade_dict = request.data.get('trade', '')
        except:
            return Response({'error': 'trade not found.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            car_id = request.data.get('car', '')
            car = Car.objects.get(car_id=car_id, status=Car.CarStatus.AT_LOT, inspected=True, inspection_recommendation=Car.InspectionRecommendation.SELL)
        except:
            return Response({'error': 'car not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if car.status == Car.CarStatus.SOLD:
            return Response({'error': 'car already sold.'}, status=status.HTTP_400_BAD_REQUEST)

        trade_in = None
        if trade_dict['vin']:
            trade_serializer = TradeInSerializer(data=trade_dict)
            if trade_serializer.is_valid():
                trade_serializer.save()
                trade_in = trade_serializer.data['car_id']
            else:
                return Response(trade_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        data['trade_in'] = trade_in
        data['seller'] = get_user_from_session(request)
        serializer = SalesSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            car.status = Car.CarStatus.SOLD
            car.save()
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def get_modes(self, request):
        modes = [{'value': mode[0], 'label': mode[1]} for mode in Sales.ModeOfSale.choices]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def delivery_modes(self, request):
        modes = [{'value': mode[0], 'label': mode[1]} for mode in Sales.ModeOfDelivery.choices]
        results = self.paginate_queryset(modes)
        serializer = ValueLabelDisplaySerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def commission_paid(self, request):
        seller = request.query_params.get('seller', None)
        if seller is not None:
            queryset = self.get_queryset().filter(seller=seller, commission_paid=True)
        else:
            queryset = self.get_queryset().filter(commission_paid=True)
        start = request.query_params.get('start_date', "")
        end = request.query_params.get('end_date', "")
        date_pattern = re.compile("^\d{4}-\d{2}-\d{2}$")
        if re.match(date_pattern, start):
            start = datetime.strptime(start, '%Y-%m-%d').date()
            queryset = queryset.filter(commission_paid_timestamp__gte=start)
        if re.match(date_pattern, end):
            end = datetime.strptime(end, '%Y-%m-%d').date()
            queryset = queryset.filter(commission_paid_timestamp__lte=end)
        results = self.paginate_queryset(queryset)
        serializer = CommissionPayableSerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def commission_unpaid(self, request):
        seller = request.query_params.get('seller', None)
        if seller is not None:
            queryset = self.get_queryset().filter(seller=seller, status=Sales.SalesStatus.FUNDED, commission_paid=False)
        else:
            queryset = self.get_queryset().filter(status=Sales.SalesStatus.FUNDED, commission_paid=False)
        results = self.paginate_queryset(queryset)
        serializer = CommissionPayableSerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def title_sales(self, request):
        sales_id = request.data.get('sales_id')
        try:
            sales = self.get_queryset().get(sales_id=sales_id, status=Sales.SalesStatus.FUNDED)
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        sales.is_titled = True
        sales.save()
        return Response({'status': 'sales titled.'}, status=status.HTTP_200_OK)  


    @action(detail=False, methods=['post'])
    def fund_sales(self, request):
        sales_id = request.data.get('sales_id')
        try:
            sales = self.get_queryset().get(sales_id=sales_id, status=Sales.SalesStatus.SOLD)
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        sales.status=Sales.SalesStatus.FUNDED
        sales.funded_timestamp=datetime.now()
        sales.save()
        return Response({'status': 'sales funded.'}, status=status.HTTP_200_OK)    

    @action(detail=False, methods=['post'])
    def cancel_sales(self, request):
        sales_id = request.data.get('sales_id')
        try:
            sales = self.get_queryset().get(sales_id=sales_id, status=Sales.SalesStatus.SOLD)
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        sales.status=Sales.SalesStatus.CANCELLED
        sales.save()
        return Response({'status': 'sales cancelled.'}, status=status.HTTP_200_OK) 

    @action(detail=False, methods=['post'])
    def deliver_sales(self, request):
        sales_id = request.data.get('sales_id')
        try:
            sales = self.get_queryset().get(sales_id=sales_id, status=Sales.SalesStatus.FUNDED)
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        sales.is_delivered = True
        sales.save()
        return Response({'status': 'sales delivered.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def get_sold(self, request):
        seller = get_user_from_session(request)
        sales = self.get_queryset().filter(seller=seller).exclude(status=Sales.SalesStatus.CANCELLED)
        cars = [sale.car for sale in sales]
        results = self.paginate_queryset(cars)
        serializer = CarSerializer(results, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_payment(self, request):
        payment = {'sales': request.data.get('sales_id'), 
                   'amount': request.data.get('amount'),
                   'payment_mode': request.data.get('payment_mode')}
        
        serializer = PaymentSerializer(data=payment, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def get_payments(self, request):
        try:
            sales = self.get_queryset().get(sales_id=request.query_params.get('sales_id'))
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)

        results = self.paginate_queryset(sales.payments.all())
        serializer = PaymentSerializer(results, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_totals(self, request):
        try:
            sales = self.get_queryset().get(sales_id=request.query_params.get('sales_id'))
        except:
            return Response({'error': 'sales not found.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TotalPaymentSerializer({'total_selling_price': sales.total_selling_price,
                                             'total_payment': sales.total_payment,
                                             'balance': sales.balance})
        return Response(serializer.data)


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.action == 'create_promised_task':
            permission_classes = [IsSalesRep]
        elif self.action == 'assign_task':
            permission_classes = [IsOperationsManager]
        elif self.action == 'create_inspection_task':
            permission_classes = [IsOperationsManager|IsOperationsTeam]
        elif self.action == 'get_assigned_task' or self.action == 'complete_task':
            permission_classes = [IsVendor|IsOperationsTeam]
        else:
            permission_classes = [IsLoggedIn]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Task.objects.filter(car__inspection_recommendation=Car.InspectionRecommendation.SELL)
        requested_by = get_user_from_session(self.request)
        usergroup = get_usergroup_from_session(self.request)
        if usergroup == User.UserGroup.OPERATIONS_TEAM or usergroup == User.UserGroup.VENDOR:
            queryset = queryset.filter(assigned_to=requested_by)
        elif usergroup == User.UserGroup.SALES_REPRESENTATIVE:
            queryset = queryset.filter(requested_by=requested_by)
        car_id = self.request.query_params.get('car_id')
        sales_id = self.request.query_params.get('sales_id')
        status = self.request.query_params.get('status')
        assigned_to = self.request.query_params.get('assigned_to')
        if car_id is not None:
            queryset = queryset.filter(car=car_id)
        if sales_id is not None:
            queryset = queryset.filter(sales=sales_id)
        if status is not None:
            if status == 'UD':
                now = datetime.now()
                queryset = queryset.filter(set_deadline__lte=now, status=Task.TaskStatus.WORK_IN_PROGRESS)
            else:
                queryset = queryset.filter(status=status)
        return queryset

    @action(detail=False, methods=['get'])
    def get_assigned_tasks(self, request):
        user_id = get_user_from_session(request)
        try:
            user = User.objects.get(user_id=user_id)
        except:
            return Response({'error': 'user not found.'}, status=status.HTTP_400_BAD_REQUEST)
       
        tasks = user.assigned_tasks.filter(status=Task.TaskStatus.WORK_IN_PROGRESS)
        results = self.paginate_queryset(tasks)
        serializer = TaskSerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_promised_tasks(self, request):
        tasks = self.get_queryset().exclude(sales=None)
        results = self.paginate_queryset(tasks)
        serializer = TaskSerializer(results, many=True, context={'request': request}) 
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_promised_task(self, request):
        task = {}
        sales_id = request.data.get('sales_id')
        requested_by = get_user_from_session(request)
        
        try:
            sales = Sales.objects.get(sales_id=sales_id, status=Sales.SalesStatus.SOLD)
        except:
            return Response({'error': 'incorrect sales found.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not requested_by == sales.seller.user_id:
            return Response({'error': 'requester is not seller.'}, status=status.HTTP_400_BAD_REQUEST)
        
        task['title'] = request.data.get('title')
        task['description'] = request.data.get('description')
        task['attached_image'] = request.FILES.get('attached_image')
        task['sales'] = sales.sales_id
        task['car'] = sales.car.car_id
        task['requested_by'] = requested_by
        task['task_type'] = Task.TaskType.PROMISED_TASK
        
        serializer = TaskSerializer(data=task, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def create_inspection_task(self, request):
        task = {}
        car_id = request.data.get('car_id')
        title = request.data.get('title')
        description = request.data.get('description')
        attached_image = request.FILES.get('attached_image')
        requested_by = get_user_from_session(request)
        
        try:
            car = Car.objects.get(car_id=car_id, status=Car.CarStatus.AT_LOT, inspected=False)
        except:
            return Response({'error': 'no car found.'}, status=status.HTTP_400_BAD_REQUEST)

        task['car'] = car_id
        task['title'] = title
        task['description'] = description
        task['requested_by'] = requested_by
        task['attached_image'] = attached_image
        task['status'] = Task.TaskStatus.PENDING_APPROVAL
        task['task_type'] = Task.TaskType.INSPECTION_TASK
        
        serializer = TaskSerializer(data=task, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def assign_task(self, request):
        task_id = request.data.get('task_id')
        assignee_id = request.data.get('assigned_to')
        set_deadline = request.data.get('set_deadline')
        approver_id = get_user_from_session(request)

        try:
            assigned_to = User.objects.get(Q(usergroup=User.UserGroup.OPERATIONS_TEAM) | Q(usergroup=User.UserGroup.VENDOR), user_id=assignee_id)
        except:
            return Response({'error': 'no operations member/vendor found.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            approved_by = User.objects.get(usergroup=User.UserGroup.OPERATIONS_MANAGER, user_id=approver_id)
        except:
            return Response({'error': 'approver is not an operations manager.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            task = self.get_queryset().get(task_id=task_id, status=Task.TaskStatus.PENDING_APPROVAL)
        except:
            return Response({'error': 'no task found.'}, status=status.HTTP_400_BAD_REQUEST)

        taskapproved_by = approved_by
        task.assigned_to = assigned_to
        task.status = Task.TaskStatus.WORK_IN_PROGRESS
        task.assigned_timestamp = datetime.now()
        task.set_deadline = set_deadline
        task.save()

        return Response({'status': 'task assigned.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def complete_task(self, request):
        task_id = request.data.get('task_id')
        attached_image = request.FILES.get('attached_image')
        assignee_id = get_user_from_session(request)

        try:
            assigned_to = User.objects.get(Q(usergroup=User.UserGroup.OPERATIONS_TEAM) | Q(usergroup=User.UserGroup.VENDOR), user_id=assignee_id)
        except:
            return Response({'error': 'no operations member/vendor found.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = self.get_queryset().get(task_id=task_id, status=Task.TaskStatus.WORK_IN_PROGRESS, assigned_to=assignee_id)
        except:
            return Response({'error': 'no task found.'}, status=status.HTTP_400_BAD_REQUEST)

        task.completion_image=attached_image 
        task.status=Task.TaskStatus.COMPLETED
        
        if task.status == Task.TaskType.STATE_INSPECTION_TASK:
            car = task.car
            car.state_inspected = True
            car.save()

        task.save()

        return Response({'status': 'task status updated.'}, status=status.HTTP_200_OK) 