from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import (
    User,
    UserRole,
    AccountStatus,
    Cluster,
    ClusterType,
    CollectorProfile,
    PickupRequest,
    PickupStatus,
    ClusterAssistance,
    AssistanceStatus,
    Wallet,
    LedgerEntry,
    TransactionStatus,
    AwarenessCampaign,
    WaitlistEntry, 
    OrganizationProfile,
    EvacuationSchedule
)

@admin.register(AwarenessCampaign)
class AwarenessCampaignAdmin(ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('created_at',)
    fieldsets = [
        ('Campaign Overview', {
            'fields': ('title', 'created_at')
        }),
        ('Rich Text Campaign Content', {
            'description': 'Draft rich educational and policy announcements using formatting, links, and media.',
            'fields': ('description',)
        }),
    ]

@admin.register(PickupRequest)
class PickupRequestAdmin(ModelAdmin):
    list_display = (
        'tracking_num', 
        'resident', 
        'cluster', 
        'assigned_collector', 
        'status_badge', 
        'fixed_service_fee', 
        'sla_due_at',
        'created_at'
    )
    list_filter = ('status', 'cluster', 'waste_volume_est')
    list_filter_submit = True
    search_fields = ('tracking_num', 'resident__email', 'pickup_address')
    readonly_fields = ('created_at', 'updated_at', 'sla_breached_at', 'completed_at')
    fieldsets = [
        ('Intake & Tracking', {
            'fields': ('tracking_num', 'resident', 'status', 'waste_volume_est')
        }),
        ('Dispatch & Location Routing', {
            'fields': ('cluster', 'assigned_collector', 'pickup_address', ('latitude', 'longitude'))
        }),
        ('Financial Settlement', {
            'fields': ('fixed_service_fee',)
        }),
        ('SLA Lifecycle & Timestamps', {
            'fields': ('sla_due_at', 'sla_breached_at', 'completed_at', 'created_at', 'updated_at')
        }),
    ]

    @display(
        description="Status",
        label={
            PickupStatus.PENDING: "warning",
            PickupStatus.ASSIGNED: "info",
            PickupStatus.IN_TRANSIT: "info",
            PickupStatus.ARRIVED: "info",
            PickupStatus.COMPLETED: "success",
            PickupStatus.CANCELLED: "danger",
            PickupStatus.SLA_BREACHED: "danger",
            PickupStatus.RE_DISPATCHED: "warning",
        }
    )
    def status_badge(self, obj):
        return obj.status

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role_badge', 'status_badge', 'cluster', 'is_staff')
    list_filter = ('role', 'status', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'phone', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    fieldsets = [
        ('Account Credentials', {
            'fields': ('email', 'username', 'password')
        }),
        ('Profile & Assignment', {
            'fields': (('first_name', 'last_name'), 'phone', 'role', 'status', 'cluster')
        }),
        ('Permissions & Staff Access', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Session Timestamps', {
            'fields': ('last_login', 'date_joined')
        }),
    ]

    @display(
        description="Role",
        label={
            UserRole.SYSTEM_ADMIN: "danger",
            UserRole.GOVT_SUPERVISOR: "info",
            UserRole.COLLECTOR_ADMIN: "success",
            UserRole.COLLECTOR_DRIVER: "success",
            UserRole.RESIDENT: "warning",
        }
    )
    def role_badge(self, obj):
        return obj.role

    @display(
        description="Status",
        label={
            AccountStatus.ACTIVE: "success",
            AccountStatus.PENDING_VERIFICATION: "warning",
            AccountStatus.SUSPENDED: "danger",
            AccountStatus.DEACTIVATED: "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

@admin.register(Cluster)
class ClusterAdmin(ModelAdmin):
    list_display = ('name', 'code', 'cluster_type_badge', 'assigned_primary_collector', 'is_locked_badge', 'created_at')
    list_filter = ('cluster_type', 'is_locked')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = [
        ('Cluster Identification', {
            'fields': ('name', 'code', 'cluster_type', 'is_locked')
        }),
        ('Primary Collector Assignment', {
            'fields': ('assigned_primary_collector',)
        }),
        ('Geographic Boundaries (GeoJSON)', {
            'fields': ('boundary_geojson',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    ]

    @display(
        description="Type",
        label={
            ClusterType.GOVERNMENT_EXCLUSIVE: "danger",
            ClusterType.COMMERCIAL_SHARED: "info",
            ClusterType.OPEN_ZONE: "success",
        }
    )
    def cluster_type_badge(self, obj):
        return obj.cluster_type

    @display(
        description="Locked",
        label={
            True: "warning",
            False: "success",
        }
    )
    def is_locked_badge(self, obj):
        return "Locked" if obj.is_locked else "Unlocked"

@admin.register(CollectorProfile)
class CollectorProfileAdmin(ModelAdmin):
    list_display = (
        'organization_name', 
        'user', 
        'operating_license_num', 
        'vehicle_capacity_tons', 
        'vehicle_plate_num', 
        'availability_badge'
    )
    list_filter = ('is_available',)
    search_fields = ('organization_name', 'operating_license_num', 'vehicle_plate_num', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = [
        ('Collector Organization', {
            'fields': ('user', 'organization_name', 'operating_license_num')
        }),
        ('Fleet Capacity & Availability', {
            'fields': ('vehicle_capacity_tons', 'vehicle_plate_num', 'is_available')
        }),
        ('Live Telemetry GPS Coordinates', {
            'fields': (('current_lat', 'current_lng'),)
        }),
        ('Audit Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    ]

    @display(
        description="Availability",
        label={
            True: "success",
            False: "danger",
        }
    )
    def availability_badge(self, obj):
        return "Available" if obj.is_available else "Busy"

@admin.register(ClusterAssistance)
class ClusterAssistanceAdmin(ModelAdmin):
    list_display = ('request', 'origin_cluster', 'assisting_collector', 'status_badge', 'created_at')
    list_filter = ('status', 'origin_cluster')
    search_fields = ('request__tracking_num', 'reason')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = [
        ('Dispatch Assistance Request', {
            'fields': ('request', 'origin_cluster', 'assisting_collector', 'status')
        }),
        ('Operational Reason & Details', {
            'fields': ('reason',)
        }),
        ('Audit Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    ]

    @display(
        description="Status",
        label={
            AssistanceStatus.REQUESTED: "warning",
            AssistanceStatus.APPROVED: "success",
            AssistanceStatus.DECLINED: "danger",
            AssistanceStatus.RESOLVED: "info",
        }
    )
    def status_badge(self, obj):
        return obj.status

@admin.register(Wallet)
class WalletAdmin(ModelAdmin):
    list_display = ('user', 'balance_formatted', 'currency', 'updated_at')
    search_fields = ('user__email',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = [
        ('Wallet Ownership & Balance', {
            'fields': ('user', 'balance', 'currency')
        }),
        ('Audit Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    ]

    @display(description="Balance")
    def balance_formatted(self, obj):
        return f"{obj.currency} {obj.balance:,.2f}"

@admin.register(LedgerEntry)
class LedgerEntryAdmin(ModelAdmin):
    list_display = (
        'reference', 
        'wallet', 
        'type', 
        'status_badge', 
        'amount_formatted', 
        'fee', 
        'created_at'
    )
    list_filter = ('type', 'status')
    search_fields = ('reference', 'wallet__user__email', 'description')
    readonly_fields = ('created_at',)
    fieldsets = [
        ('Transaction Identification', {
            'fields': ('reference', 'wallet', 'pickup_request', 'type', 'status')
        }),
        ('Financial Audit', {
            'fields': ('amount', 'fee', 'description')
        }),
        ('Transaction Metadata', {
            'fields': ('metadata',)
        }),
        ('Audit Timestamp', {
            'fields': ('created_at',)
        }),
    ]

    @display(
        description="Status",
        label={
            TransactionStatus.SUCCESSFUL: "success",
            TransactionStatus.PENDING: "warning",
            TransactionStatus.PROCESSING: "info",
            TransactionStatus.FAILED: "danger",
            TransactionStatus.REVERSED: "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @display(description="Amount")
    def amount_formatted(self, obj):
        return f"{obj.amount:,.2f}"

@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(ModelAdmin):
    list_display = ("area_name", "phone", "email", "created_at")
    search_fields = ("area_name", "phone", "email")

@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(ModelAdmin):
    list_display = ("facility_name", "officer_in_charge", "created_at")
    search_fields = ("facility_name", "officer_in_charge")

@admin.register(EvacuationSchedule)
class EvacuationScheduleAdmin(ModelAdmin):
    list_display = ("organization", "frequency", "preferred_window", "is_active")
    list_filter = ("frequency", "is_active")