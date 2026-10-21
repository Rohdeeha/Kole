from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CollectorProfile, Cluster, UserRole, PickupRequest,WaitlistEntry, OrganizationProfile, EvacuationSchedule, LedgerEntry

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'role', 'status', 'cluster']
        read_only_fields = ['id', 'status', 'role']

class CollectorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorProfile
        fields = [
            'organization_name', 'operating_license_num', 'vehicle_capacity_tons',
            'vehicle_plate_num'
        ]

class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    collector_profile = CollectorProfileSerializer(required=False)
    cluster_code = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'phone', 'role', 'collector_profile', 'cluster_code']

    def create(self, validated_data):
        profile_data = validated_data.pop('collector_profile', None)
        cluster_code = validated_data.pop('cluster_code', None)
        
        # Handle cluster assignment
        if cluster_code:
            try:
                cluster = Cluster.objects.get(code=cluster_code)
                validated_data['cluster'] = cluster
            except Cluster.DoesNotExist:
                raise serializers.ValidationError({"cluster_code": "Invalid cluster code."})

        # Set username to email since we are using email as USERNAME_FIELD
        if 'username' not in validated_data:
            validated_data['username'] = validated_data['email']
            
        role = validated_data.get('role', UserRole.RESIDENT)
        
        user = User.objects.create_user(**validated_data)
        
        if role in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN] and profile_data:
            CollectorProfile.objects.create(user=user, **profile_data)
            
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['success'] = True
        data['accessToken'] = data.pop('access')
        data['refreshToken'] = data.pop('refresh')
        return data


class PickupRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupRequest
        fields = '__all__'


class CreatePickupRequestSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=500)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)
    wasteVolume = serializers.CharField(max_length=50, default='STANDARD_BIN')
    proof_image = serializers.ImageField(required=False)

    class Meta:
        model = PickupRequest
        fields = ['address', 'latitude', 'longitude', 'wasteVolume', 'proof_image']

class WaitlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaitlistEntry
        fields = ['id', 'email', 'phone', 'area_name', 'notes', 'created_at']


class OrganizationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'facility_name', 'officer_in_charge', 'staging_bay_notes', 'waste_categories']


class EvacuationScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvacuationSchedule
        fields = ['id', 'organization', 'frequency', 'preferred_window', 'is_active']


class AdminMetricsSerializer(serializers.Serializer):
    gross_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    tonnage_cleared = serializers.DecimalField(max_digits=8, decimal_places=2)
    active_pickups_count = serializers.IntegerField()


class SettlementOverviewSerializer(serializers.ModelSerializer):
    collector_name = serializers.CharField(source='pickup_request.assigned_collector.collector_profile.organization_name', read_only=True)
    tracking_num = serializers.CharField(source='pickup_request.tracking_num', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'reference', 'tracking_num', 'collector_name', 
            'amount', 'collector_share', 'platform_commission', 'status', 'created_at'
        ]   

class PaymentInitializeSerializer(serializers.Serializer):
    amount = serializers.FloatField(min_value=100.0)
    callback_url = serializers.URLField(required=False)


class PaymentVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)         

