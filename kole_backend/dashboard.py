from core.models import (
    PickupRequest,
    CollectorProfile,
    Cluster,
    User,
    Wallet,
    WaitlistEntry,
    ClusterAssistance,
    OrganizationProfile,
    EvacuationSchedule,
)

def dashboard_callback(request, context):
    """
    Supplies situational metrics and KPIs to the Unfold admin dashboard
    while clearing redundant app_list duplication.
    """
    try:
        kpi = {
            "pickup_total": PickupRequest.objects.count(),
            "pickup_pending": PickupRequest.objects.filter(status='PENDING').count(),
            "collectors_count": CollectorProfile.objects.count(),
            "clusters_count": Cluster.objects.count(),
            "users_count": User.objects.count(),
            "assistances_count": ClusterAssistance.objects.filter(status='REQUESTED').count(),
            "organizations_count": OrganizationProfile.objects.count(),
            "waitlist_count": WaitlistEntry.objects.count(),
            "evacuations_count": EvacuationSchedule.objects.filter(is_active=True).count(),
        }
    except Exception:
        kpi = {
            "pickup_total": 0,
            "pickup_pending": 0,
            "collectors_count": 0,
            "clusters_count": 0,
            "users_count": 0,
            "assistances_count": 0,
            "organizations_count": 0,
            "waitlist_count": 0,
            "evacuations_count": 0,
        }

    context["kpi"] = kpi
    # Remove redundant model list from the main dashboard
    context["app_list"] = []
    return context
