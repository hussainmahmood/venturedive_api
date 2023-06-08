from rest_framework import serializers
from datetime import datetime
from .models import User, ModeOfPayment, Warranty, Insurance, Car, CarImage, Sales, Payment, Task

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        fields = self.context['request'].query_params.get('fields')
        if fields:
            fields = fields.split(',')
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

class PasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField()
    new_password = serializers.CharField(read_only=True)
    
    class Meta:
        model = User

    
class UserDisplaySerializer(DynamicFieldsModelSerializer):
    usergroup_display = serializers.SerializerMethodField()
    class Meta:
        model = User
        exclude = ['password']

    def get_usergroup_display(self, instance):
        choice = User.UserGroup(value=instance.usergroup)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

class ValueLabelDisplaySerializer(serializers.Serializer):
    value = serializers.CharField(max_length=2)
    label = serializers.CharField()

class ModeOfPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeOfPayment
        fields = "__all__"

class WarrantySerializer(serializers.ModelSerializer):
    class Meta:
        model = Warranty
        fields = "__all__"


class InsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insurance
        fields = "__all__"

class CarImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarImage
        fields = "__all__"

class CarSerializer(DynamicFieldsModelSerializer):
    thumbnail = serializers.ImageField(max_length=None, use_url=True, allow_null=True, required=False)
    status_display = serializers.SerializerMethodField()
    class Meta:
        model = Car
        fields = "__all__"

    def get_status_display(self, instance):
        choice = Car.CarStatus(value=instance.status)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())

class InspectedCarSerializer(CarSerializer):
    no_of_tasks = serializers.CharField(max_length=None, allow_null=True, required=False)

class TradeInSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = ['car_id', 'vin', 'make', 'model', 'year', 'book_price']
        extra_kwargs = {'vin': {'max_length': 17}, 'book_price': {'required': True}} 

class SalesSerializer(DynamicFieldsModelSerializer):
    vin = serializers.ReadOnlyField(source='car.vin')
    seller_name = serializers.ReadOnlyField(source='seller.name')
    mode_of_sale_display = serializers.SerializerMethodField()
    mode_of_delivery_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    total_payment = serializers.DecimalField(max_digits=11, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=11, decimal_places=2, read_only=True)

    
    class Meta:
        model = Sales
        fields = "__all__"

    def get_mode_of_sale_display(self, instance):
        choice = Sales.ModeOfSale(value=instance.mode_of_sale)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())

    def get_mode_of_delivery_display(self, instance):
        choice = Sales.ModeOfDelivery(value=instance.mode_of_delivery)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())

    def get_status_display(self, instance):
        choice = Sales.SalesStatus(value=instance.status)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())

class PaymentSerializer(serializers.ModelSerializer):
    mode = serializers.ReadOnlyField(source='payment_mode.name')
    class Meta:
        model = Payment
        fields = "__all__"

class TotalPaymentSerializer(serializers.Serializer):
    total_selling_price = serializers.DecimalField(max_digits=11, decimal_places=2, read_only=True)
    total_payment = serializers.DecimalField(max_digits=11, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=11, decimal_places=2, read_only=True)


class TaskSerializer(serializers.ModelSerializer):
    vin = serializers.ReadOnlyField(source='car.vin')
    requester = serializers.ReadOnlyField(source='requested_by.name')
    approver = serializers.ReadOnlyField(source='approved_by.name')
    assignee = serializers.ReadOnlyField(source='assigned_to.name')
    status_display = serializers.SerializerMethodField()
    attached_image = serializers.ImageField(max_length=None, use_url=True, allow_null=False, required=True)
    class Meta:
        model = Task
        fields = "__all__"

    def get_status_display(self, instance):
        choice = Task.TaskStatus(value=instance.status)
        return ' '.join(word.capitalize() for word in choice.name.replace("_", " ").split())



### DISPLAY SERIALIZERS ###

class LoginSerializer(serializers.Serializer):
    session = serializers.CharField(read_only=True)
    usergroup = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    usergroup_display = serializers.CharField(read_only=True)

class SalesPerformanceSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    sales_count = serializers.CharField(read_only=True)
    insurance_count = serializers.CharField(read_only=True)
    warranty_count = serializers.CharField(read_only=True)

class CommissionPayableSerializer(serializers.ModelSerializer):
    vin = serializers.ReadOnlyField(source='car.vin')
    seller_name = serializers.ReadOnlyField(source='seller.name')
    class Meta:
        model = Sales
        fields = ['vin', 'seller_name', 'warranty_sold', 'insurance_sold', 'commission']