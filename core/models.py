import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from ckeditor.fields import RichTextField

# ==============================================================================
# ENUMS & TEXT CHOICES
# ==============================================================================

class UserRole(models.TextChoices):
    RESIDENT = 'RESIDENT', 'Resident'
    ORGANIZATION = 'ORGANIZATION', 'Commercial / Organization'
    COLLECTOR_DRIVER = 'COLLECTOR_DRIVER', 'Collector Driver'
    COLLECTOR_ADMIN = 'COLLECTOR_ADMIN', 'Collector Admin'
    GOVT_SUPERVISOR = 'GOVT_SUPERVISOR', 'Government Supervisor'
    SYSTEM_ADMIN = 'SYSTEM_ADMIN', 'System Admin'


class AccountStatus(models.TextChoices):
    PENDING_VERIFICATION = 'PENDING_VERIFICATION', 'Pending Verification'
    ACTIVE = 'ACTIVE', 'Active'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    DEACTIVATED = 'DEACTIVATED', 'Deactivated'


class ClusterType(models.TextChoices):
    GOVERNMENT_EXCLUSIVE = 'GOVERNMENT_EXCLUSIVE', 'Government Exclusive'
    COMMERCIAL_SHARED = 'COMMERCIAL_SHARED', 'Commercial Shared'
    OPEN_ZONE = 'OPEN_ZONE', 'Open Zone'


class PickupStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PENDING_QUOTE = 'PENDING_QUOTE', 'Pending Quote'
    QUOTED = 'QUOTED', 'Quoted'
    ASSIGNED = 'ASSIGNED', 'Assigned'
    IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
    ARRIVED = 'ARRIVED', 'Arrived'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    SLA_BREACHED = 'SLA_BREACHED', 'SLA Breached'
    RE_DISPATCHED = 'RE_DISPATCHED', 'Re-dispatched'


class PaymentStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'Unpaid'
    PENDING = 'PENDING', 'Pending'
    PAID = 'PAID', 'Paid'
    REFUNDED = 'REFUNDED', 'Refunded'


class AssistanceStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', 'Requested'
    APPROVED = 'APPROVED', 'Approved'
    DECLINED = 'DECLINED', 'Declined'
    RESOLVED = 'RESOLVED', 'Resolved'


class TransactionType(models.TextChoices):
    SERVICE_FEE = 'SERVICE_FEE', 'Service Fee'
    GOVT_SUBSIDY = 'GOVT_SUBSIDY', 'Govt Subsidy'
    DISPATCH_PAYOUT = 'DISPATCH_PAYOUT', 'Dispatch Payout'
    REFUND = 'REFUND', 'Refund'
    SYSTEM_ADJUSTMENT = 'SYSTEM_ADJUSTMENT', 'System Adjustment'


class TransactionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    SUCCESSFUL = 'SUCCESSFUL', 'Successful'
    FAILED = 'FAILED', 'Failed'
    REVERSED = 'REVERSED', 'Reversed'


class EvacuationFrequency(models.TextChoices):
    ON_DEMAND = 'ON_DEMAND', 'On Demand'
    WEEKLY = 'WEEKLY', 'Weekly'
    BI_WEEKLY = 'BI_WEEKLY', 'Bi-Weekly'
    MONTHLY = 'MONTHLY', 'Monthly'


class PreferredWindow(models.TextChoices):
    MORNING = 'MORNING', 'Morning (8AM - 12PM)'
    AFTERNOON = 'AFTERNOON', 'Afternoon (12PM - 4PM)'


# ==============================================================================
# CORE & USER MODELS
# ==============================================================================

class Cluster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True)
    cluster_type = models.CharField(
        max_length=50, choices=ClusterType.choices, default=ClusterType.GOVERNMENT_EXCLUSIVE
    )
    
    # Geographic boundaries per phase 1 requirements (GeoJSON format)
    boundary_geojson = models.JSONField(null=True, blank=True)
    
    assigned_primary_collector = models.ForeignKey(
        'core.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='primary_clusters'
    )
    is_locked = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    role = models.CharField(max_length=50, choices=UserRole.choices, default=UserRole.RESIDENT)
    status = models.CharField(max_length=50, choices=AccountStatus.choices, default=AccountStatus.PENDING_VERIFICATION)
    
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email


class CollectorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='collector_profile')
    organization_name = models.CharField(max_length=255)
    operating_license_num = models.CharField(max_length=100, unique=True)
    vehicle_capacity_tons = models.DecimalField(max_digits=8, decimal_places=2, default=1.00)
    vehicle_plate_num = models.CharField(max_length=50, null=True, blank=True)
    is_available = models.BooleanField(default=True)
    
    # Paystack Subaccount integration for direct automated payout split
    paystack_subaccount_code = models.CharField(max_length=100, null=True, blank=True, help_text="e.g. ACCT_xxxxxxx")
    settlement_bank = models.CharField(max_length=100, null=True, blank=True)
    bank_code = models.CharField(max_length=20, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    account_name = models.CharField(max_length=150, null=True, blank=True)
    
    # Location matching geographic cluster constraints
    current_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    current_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.organization_name


# ==============================================================================
# DISPATCH & OPERATIONAL MODELS
# ==============================================================================

class PickupRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracking_num = models.CharField(max_length=36, unique=True)
    resident = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pickup_requests')
    cluster = models.ForeignKey(Cluster, on_delete=models.RESTRICT, related_name='cluster_pickups')
    assigned_collector = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_pickups'
    )
    status = models.CharField(max_length=50, choices=PickupStatus.choices, default=PickupStatus.PENDING)
    payment_status = models.CharField(max_length=50, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    
    is_emergency = models.BooleanField(default=False)
    pickup_address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    waste_volume_est = models.CharField(max_length=50, default='STANDARD_BIN')
    fixed_service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=1500.00)
    quote_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    sla_due_at = models.DateTimeField()
    sla_breached_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    proof_image = models.ImageField(upload_to='kole_pickups/', null=True, blank=True)
    def __str__(self):
        return f"{self.tracking_num} ({self.status})"


class ClusterAssistance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(PickupRequest, on_delete=models.CASCADE, related_name='assistances')
    origin_cluster = models.ForeignKey(Cluster, on_delete=models.RESTRICT)
    assisting_collector = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, choices=AssistanceStatus.choices, default=AssistanceStatus.REQUESTED)
    reason = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Assistance #{self.id} for {self.request.tracking_num}"


# ==============================================================================
# COMMERCIAL & STAGING BAY MODULE
# ==============================================================================

class OrganizationProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization_profile')
    facility_name = models.CharField(max_length=255)  # e.g., "Oroki Innovation Hub"
    officer_in_charge = models.CharField(max_length=150)
    staging_bay_notes = models.TextField(help_text="e.g., Rear loading dock near generator house", blank=True, null=True)
    waste_categories = models.JSONField(default=list, help_text="e.g., ['Cardboard', 'E-Waste', 'Plastics']")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.facility_name


class EvacuationSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(OrganizationProfile, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(max_length=30, choices=EvacuationFrequency.choices, default=EvacuationFrequency.WEEKLY)
    preferred_window = models.CharField(max_length=30, choices=PreferredWindow.choices, default=PreferredWindow.MORNING)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.facility_name} - {self.frequency}"


# ==============================================================================
# WAITLIST & HEATMAP MODULE
# ==============================================================================

class WaitlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20)
    area_name = models.CharField(max_length=150, help_text="e.g. Owode Ede, Akepe")
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='waitlist_entries')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Waitlist entries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.area_name} ({self.phone})"


# ==============================================================================
# FINANCIAL & LEDGER MODULE
# ==============================================================================

class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default='NGN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} Wallet (₦{self.balance})"


class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=100, unique=True)  # Paystack reference or internal transaction ID
    wallet = models.ForeignKey(Wallet, on_delete=models.RESTRICT, related_name='ledger_entries')
    pickup_request = models.ForeignKey(PickupRequest, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=50, choices=TransactionType.choices)
    status = models.CharField(max_length=50, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # Total collected
    collector_share = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, help_text="80% split share")
    platform_commission = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, help_text="20% platform fee")
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    
    description = models.TextField()
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Ledger entries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} - ₦{self.amount} ({self.status})"


# ==============================================================================
# MARKETING & OUTREACH
# ==============================================================================

class AwarenessCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = RichTextField()  # CKEditor rich text field
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title