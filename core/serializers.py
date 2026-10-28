import logging
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    CollectorProfile, Cluster, UserRole, PickupRequest, PickupStatus,
    WaitlistEntry, OrganizationProfile, EvacuationSchedule, LedgerEntry, Wallet
)
from .paystack import PaystackService

logger = logging.getLogger(__name__)
User = get_user_model()


class ClusterSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = ['id', 'name', 'code', 'cluster_type', 'is_locked']


class CollectorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorProfile
        fields = [
            'id', 'organization_name', 'operating_license_num', 'vehicle_capacity_tons',
            'vehicle_plate_num', 'is_available', 'settlement_bank', 'bank_code',
            'account_number', 'account_name', 'paystack_subaccount_code',
            'current_lat', 'current_lng'
        ]
        read_only_fields = ['id', 'paystack_subaccount_code']


class OrganizationProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationProfile
        fields = ['id', 'facility_name', 'officer_in_charge', 'staging_bay_notes', 'waste_categories']


class UserSerializer(serializers.ModelSerializer):
    cluster_details = ClusterSimpleSerializer(source='cluster', read_only=True)
    collector_profile = CollectorProfileSerializer(read_only=True)
    organization_profile = OrganizationProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'phone',
            'role', 'status', 'cluster', 'cluster_details',
            'collector_profile', 'organization_profile'
        ]
        read_only_fields = ['id', 'status', 'role']


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    collector_profile = CollectorProfileSerializer(required=False)
    cluster_code = serializers.CharField(write_only=True, required=False)
    cluster = serializers.PrimaryKeyRelatedField(queryset=Cluster.objects.all(), required=False)
    
    # Collector bank & details (optional at top-level)
    bank_code = serializers.CharField(write_only=True, required=False)
    account_number = serializers.CharField(write_only=True, required=False)
    account_name = serializers.CharField(write_only=True, required=False)
    organization_name = serializers.CharField(write_only=True, required=False)
    operating_license_num = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name', 'phone', 'role',
            'collector_profile', 'cluster_code', 'cluster',
            'bank_code', 'account_number', 'account_name', 'organization_name', 'operating_license_num'
        ]

    def create(self, validated_data):
        profile_data = validated_data.pop('collector_profile', {}) or {}
        cluster_code = validated_data.pop('cluster_code', None)
        direct_cluster = validated_data.pop('cluster', None)
        
        # Flatten top-level collector bank/profile fields if provided
        bank_code = validated_data.pop('bank_code', None)
        account_number = validated_data.pop('account_number', None)
        account_name = validated_data.pop('account_name', None)
        org_name = validated_data.pop('organization_name', None)
        lic_num = validated_data.pop('operating_license_num', None)

        if bank_code:
            profile_data['bank_code'] = bank_code
        if account_number:
            profile_data['account_number'] = account_number
        if account_name:
            profile_data['account_name'] = account_name
        if org_name and 'organization_name' not in profile_data:
            profile_data['organization_name'] = org_name
        if lic_num and 'operating_license_num' not in profile_data:
            profile_data['operating_license_num'] = lic_num

        # Handle cluster assignment
        if direct_cluster:
            validated_data['cluster'] = direct_cluster
        elif cluster_code:
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
        Wallet.objects.get_or_create(user=user)
        
        # Handle Collector Profile & Paystack Subaccount
        if role in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN] or profile_data:
            c_org_name = profile_data.get('organization_name') or f"{user.first_name or 'Collector'} Operations"
            c_lic_num = profile_data.get('operating_license_num') or f"LIC-{user.id.hex[:8].upper()}"
            profile_data['organization_name'] = c_org_name
            profile_data['operating_license_num'] = c_lic_num

            # Paystack subaccount creation
            b_code = profile_data.get('bank_code')
            acc_num = profile_data.get('account_number')
            if b_code and acc_num:
                try:
                    paystack = PaystackService()
                    res = paystack.create_subaccount(
                        business_name=c_org_name,
                        settlement_bank=b_code,
                        account_number=acc_num,
                        percentage_charge=20.0,
                        description=f"Kole split settlement subaccount for {c_org_name}"
                    )
                    if res.get('status') and 'data' in res:
                        profile_data['paystack_subaccount_code'] = res['data'].get('subaccount_code')
                        profile_data['settlement_bank'] = res['data'].get('settlement_bank')
                except Exception as e:
                    logger.warning(f"Failed to auto-create Paystack subaccount: {e}")

            CollectorProfile.objects.create(user=user, **profile_data)
            
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Supports email-primary login alongside username checks.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False
        self.fields['email'] = serializers.EmailField(required=False, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        login_identifier = attrs.get(self.username_field) or email

        if not login_identifier:
            raise serializers.ValidationError({"email": "Email or username is required."})

        # Try resolving user by email first, then username
        user = None
        if '@' in str(login_identifier):
            user = User.objects.filter(email__iexact=login_identifier).first()
        if not user:
            user = User.objects.filter(username__iexact=login_identifier).first()

        if user:
            attrs[self.username_field] = user.email

        data = super().validate(attrs)
        user = self.user
        data['success'] = True
        data['accessToken'] = data.pop('access')
        data['refreshToken'] = data.pop('refresh')
        data['user'] = UserSerializer(user).data
        return data


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(required=True, help_text="Google ID token")
    role = serializers.ChoiceField(choices=UserRole.choices, default=UserRole.RESIDENT, required=False)


class PickupRequestSerializer(serializers.ModelSerializer):
    resident_details = UserSerializer(source='resident', read_only=True)
    cluster_details = ClusterSimpleSerializer(source='cluster', read_only=True)
    assigned_collector_details = UserSerializer(source='assigned_collector', read_only=True)
    collector_location = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = [
            'id', 'tracking_num', 'resident', 'resident_details',
            'cluster', 'cluster_details', 'assigned_collector', 'assigned_collector_details',
            'status', 'payment_status', 'is_emergency', 'pickup_address',
            'latitude', 'longitude', 'waste_volume_est', 'fixed_service_fee',
            'quote_price', 'proof_image', 'collector_location',
            'sla_due_at', 'sla_breached_at', 'completed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tracking_num', 'resident', 'assigned_collector',
            'sla_due_at', 'sla_breached_at', 'completed_at', 'created_at', 'updated_at'
        ]

    def get_collector_location(self, obj):
        if obj.assigned_collector and hasattr(obj.assigned_collector, 'collector_profile'):
            profile = obj.assigned_collector.collector_profile
            if profile.current_lat is not None and profile.current_lng is not None:
                return {
                    'latitude': float(profile.current_lat),
                    'longitude': float(profile.current_lng)
                }
        return None


class CreatePickupRequestSerializer(serializers.Serializer):
    cluster = serializers.UUIDField(required=False, allow_null=True)
    address = serializers.CharField(max_length=500, required=False)
    pickup_address = serializers.CharField(max_length=500, required=False)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8, required=False, default=7.7825)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8, required=False, default=4.5621)
    waste_photo = serializers.FileField(required=False, allow_null=True)
    proof_image = serializers.FileField(required=False, allow_null=True)
    is_emergency = serializers.BooleanField(required=False, default=False)
    wasteVolume = serializers.CharField(max_length=50, default='STANDARD_BIN', required=False)
    waste_volume_est = serializers.CharField(max_length=50, required=False)

    def validate(self, attrs):
        address = attrs.get('address') or attrs.get('pickup_address')
        if not address:
            raise serializers.ValidationError({"address": "Pickup address is required."})
        attrs['address'] = address

        image = attrs.get('waste_photo') or attrs.get('proof_image')
        if image:
            attrs['proof_image'] = image

        waste_vol = attrs.get('waste_volume_est') or attrs.get('wasteVolume') or 'STANDARD_BIN'
        attrs['waste_volume_est'] = waste_vol

        return attrs


class QuoteSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)


class UpdateLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8)


class SubaccountSetupSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=255, required=False)
    bank_code = serializers.CharField(max_length=20)
    account_number = serializers.CharField(max_length=20)
    account_name = serializers.CharField(max_length=150, required=False)


class WaitlistSerializer(serializers.ModelSerializer):
    cluster_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    cluster = ClusterSimpleSerializer(read_only=True)

    class Meta:
        model = WaitlistEntry
        fields = ['id', 'email', 'phone', 'area_name', 'cluster', 'cluster_id', 'notes', 'created_at']

    def create(self, validated_data):
        cluster_id = validated_data.pop('cluster_id', None)
        if cluster_id:
            try:
                validated_data['cluster'] = Cluster.objects.get(id=cluster_id)
            except Cluster.DoesNotExist:
                pass
        return super().create(validated_data)


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

