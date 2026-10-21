from django.urls import path
from .views import (
    RegistrationView, 
    LoginView, 
    RequestPickupView, 
    CollectorQueueView, 
    ClaimPickupView, 
    RequestWithdrawalView,
    WaitlistCreateView, 
    AdminHeatmapView,
    OrganizationStagingView, 
    EvacuationScheduleView,
    AdminMetricsView, 
    SettlementListView,
    InitializePaymentView, 
    VerifyPaymentView
)

urlpatterns = [
    # Auth
    path('auth/register/', RegistrationView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    
    # Dispatch & Cluster APIs
    path('dispatch/request/', RequestPickupView.as_view(), name='request_pickup'),
    path('dispatch/queue/', CollectorQueueView.as_view(), name='collector_queue'),
    path('dispatch/claim/<uuid:requestId>/', ClaimPickupView.as_view(), name='claim_pickup'),
    
    # Finance APIs
    path('finance/withdraw/', RequestWithdrawalView.as_view(), name='request_withdrawal'),

    # Growth & Waitlist
    path('waitlist/', WaitlistCreateView.as_view(), name='waitlist-create'),

    # Admin Dashboard APIs
    path('admin/heatmap/', AdminHeatmapView.as_view(), name='admin-heatmap'),
    path('admin/metrics/', AdminMetricsView.as_view(), name='admin-metrics'),
    path('admin/settlements/', SettlementListView.as_view(), name='admin-settlements'),

    # Commercial & Staging Bays
    path('organization/staging-config/', OrganizationStagingView.as_view(), name='staging-config'),
    path('organization/schedule/', EvacuationScheduleView.as_view(), name='evacuation-schedule'),

    # Paystack Payments
    path('payments/initialize/', InitializePaymentView.as_view(), name='payment-initialize'),
    path('payments/verify/', VerifyPaymentView.as_view(), name='payment-verify'),
]