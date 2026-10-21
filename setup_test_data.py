import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kole_backend.settings')
django.setup()

from core.models import User, Cluster, CollectorProfile, UserRole, AccountStatus, ClusterType

# 1. Create a System Admin (Superuser)
if not User.objects.filter(email='admin@kole.ng').exists():
    admin = User.objects.create_superuser(
        email='admin@kole.ng',
        username='admin@kole.ng',
        password='adminpassword123',
        first_name='System',
        last_name='Admin',
        role=UserRole.SYSTEM_ADMIN,
        status=AccountStatus.ACTIVE
    )
    print("Created Admin: admin@kole.ng / adminpassword123")

# 2. Create a Geographic Cluster
cluster, created = Cluster.objects.get_or_create(
    code='LAG-VI-001',
    defaults={
        'name': 'Victoria Island Zone A',
        'cluster_type': ClusterType.COMMERCIAL_SHARED,
        'is_locked': True
    }
)

# 3. Create a Resident
if not User.objects.filter(email='resident@kole.ng').exists():
    resident = User.objects.create_user(
        email='resident@kole.ng',
        username='resident@kole.ng',
        password='residentpassword123',
        first_name='Ade',
        last_name='Resident',
        role=UserRole.RESIDENT,
        status=AccountStatus.ACTIVE,
        cluster=cluster
    )
    print("Created Resident: resident@kole.ng / residentpassword123")

# 4. Create a Collector
if not User.objects.filter(email='collector@kole.ng').exists():
    collector = User.objects.create_user(
        email='collector@kole.ng',
        username='collector@kole.ng',
        password='collectorpassword123',
        first_name='Tunde',
        last_name='Collector',
        role=UserRole.COLLECTOR_DRIVER,
        status=AccountStatus.ACTIVE,
        cluster=cluster
    )
    CollectorProfile.objects.create(
        user=collector,
        organization_name='Tunde Waste Management',
        operating_license_num='LIC-12345678',
        vehicle_capacity_tons=3.5,
        vehicle_plate_num='LAG-123-AB'
    )
    print("Created Collector: collector@kole.ng / collectorpassword123")

print("Test data setup complete.")
