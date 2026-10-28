from django.urls import path
from .views import (
    RegistrationView, 
    LoginView, 
    GoogleAuthView,
    PickupsView,
    PickupDetailView,
    PickupQuoteView,
    PickupUpdateLocationView,
    PickupCompleteView,
    RequestPickupView, 
    CollectorQueueView, 
    ClaimPickupView, 
    CollectorSubaccountView,
    BankListView,
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
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    
    # Pickups & Dispatch Operations
    path('pickups/', PickupsView.as_view(), name='pickups-list-create'),
    path('pickups/<uuid:pk>/', PickupDetailView.as_view(), name='pickup-detail'),
    path('pickups/<uuid:pk>/quote/', PickupQuoteView.as_view(), name='pickup-quote'),
    path('pickups/<uuid:pk>/update-location/', PickupUpdateLocationView.as_view(), name='pickup-update-location'),
    path('pickups/<uuid:pk>/complete/', PickupCompleteView.as_view(), name='pickup-complete'),

    # Legacy Dispatch & Cluster APIs
    path('dispatch/request/', RequestPickupView.as_view(), name='request_pickup'),
    path('dispatch/queue/', CollectorQueueView.as_view(), name='collector_queue'),
    path('dispatch/claim/<uuid:requestId>/', ClaimPickupView.as_view(), name='claim_pickup'),
    
    # Finance & Settlement APIs
    path('finance/subaccount/', CollectorSubaccountView.as_view(), name='collector-subaccount'),
    path('finance/banks/', BankListView.as_view(), name='bank-list'),
    path('finance/withdraw/', RequestWithdrawalView.as_view(), name='request_withdrawal'),
    path('payments/initialize/', InitializePaymentView.as_view(), name='payment-initialize'),
    path('payments/verify/', VerifyPaymentView.as_view(), name='payment-verify'),

    # Growth & Waitlist
    path('waitlist/', WaitlistCreateView.as_view(), name='waitlist-create'),

    # Commercial & Staging Bays
    path('organization/staging-config/', OrganizationStagingView.as_view(), name='staging-config'),
    path('organization/schedule/', EvacuationScheduleView.as_view(), name='evacuation-schedule'),

    # Admin Dashboard APIs
    path('admin/heatmap/', AdminHeatmapView.as_view(), name='admin-heatmap'),
    path('admin/metrics/', AdminMetricsView.as_view(), name='admin-metrics'),
    path('admin/settlements/', SettlementListView.as_view(), name='admin-settlements'),
]