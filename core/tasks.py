from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import PickupRequest, PickupStatus, ClusterAssistance, AssistanceStatus

@shared_task
def sla_inspector_job():
    """
    Automated SLA Inspector Task: Runs every 30 minutes to evaluate pending pickups, 
    detect 48-hour SLA violations, and trigger hard 72-hour escalations.
    """
    now = timezone.now()
    
    # 1. Evaluate pending/assigned pickups crossing 48h SLA
    breached_pickups = PickupRequest.objects.filter(
        status__in=[PickupStatus.PENDING, PickupStatus.ASSIGNED],
        sla_due_at__lte=now,
        sla_breached_at__isnull=True
    ).select_related('cluster')
    
    for pickup in breached_pickups:
        with transaction.atomic():
            pickup.status = PickupStatus.SLA_BREACHED
            pickup.sla_breached_at = now
            pickup.save()
            
            # Unlock cluster restrictions for this pickup by issuing ClusterAssistance
            ClusterAssistance.objects.create(
                request=pickup,
                origin_cluster=pickup.cluster,
                status=AssistanceStatus.REQUESTED,
                reason=f"Automated SLA Breach Triggered after 48h deadline failure in cluster {pickup.cluster.code}"
            )
            # In Phase 3 real-time architecture, we would dispatch a Socket.io event here.

    # 2. Hard 72-Hour Escalation Logic
    escalation_threshold = now - timedelta(hours=72)
    critical_escalations = PickupRequest.objects.filter(
        status=PickupStatus.SLA_BREACHED,
        created_at__lte=escalation_threshold
    )
    
    for pickup in critical_escalations:
        with transaction.atomic():
            pickup.status = PickupStatus.RE_DISPATCHED
            pickup.save()
            # Escalate to priority operations or secondary fleets via event bus
