import uuid
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, Count

from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    PickupRequest, PickupStatus, Wallet, LedgerEntry, 
    TransactionType, TransactionStatus, WaitlistEntry, 
    OrganizationProfile, EvacuationSchedule
)
from .serializers import (
    RegistrationSerializer, CustomTokenObtainPairSerializer,
    PickupRequestSerializer, CreatePickupRequestSerializer,
    WaitlistSerializer, OrganizationProfileSerializer, 
    EvacuationScheduleSerializer, SettlementOverviewSerializer,
    PaymentInitializeSerializer, PaymentVerifySerializer
)
from .paystack import PaystackService

User = get_user_model()


# ==============================================================================
# 1. AUTHENTICATION & REGISTRATION VIEWS
# ==============================================================================

class RegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            "success": True,
            "message": "User registered successfully.",
            "data": {
                "userId": user.id,
                "email": user.email,
                "role": user.role,
                "clusterId": user.cluster.id if user.cluster else None
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


# ==============================================================================
# 2. PICKUP REQUESTS & COLLECTOR OPERATIONS VIEWS
# ==============================================================================
from rest_framework.parsers import MultiPartParser, FormParser
class RequestPickupView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.role != 'RESIDENT' or not user.cluster:
            return Response({"success": False, "message": "Only mapped residents can request pickups."}, status=403)
            
        serializer = CreatePickupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        now = timezone.now()
        sla_due_at = now + timedelta(hours=48)
        tracking_num = f"KOL-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        
        pickup = PickupRequest.objects.create(
            tracking_num=tracking_num,
            resident=user,
            cluster=user.cluster,
            pickup_address=serializer.validated_data['address'],
            latitude=serializer.validated_data['latitude'],
            longitude=serializer.validated_data['longitude'],
            waste_volume_est=serializer.validated_data['wasteVolume'],
            fixed_service_fee=1500.00,
            sla_due_at=sla_due_at
        )
        
        return Response({
            "success": True,
            "data": {
                "requestId": pickup.id,
                "trackingNum": pickup.tracking_num,
                "status": pickup.status,
                "clusterId": pickup.cluster.id,
                "fixedServiceFee": pickup.fixed_service_fee,
                "slaDueAt": pickup.sla_due_at
            }
        }, status=status.HTTP_201_CREATED)


class CollectorQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role not in ['COLLECTOR_DRIVER', 'COLLECTOR_ADMIN'] or not user.cluster:
            return Response({"success": False, "message": "Unauthorized."}, status=403)
            
        requests = PickupRequest.objects.filter(
            cluster=user.cluster, 
            status=PickupStatus.PENDING
        )
        
        data = []
        for req in requests:
            data.append({
                "requestId": req.id,
                "trackingNum": req.tracking_num,
                "address": req.pickup_address,
                "status": req.status,
                "slaDueAt": req.sla_due_at,
                "isBreached": bool(req.sla_breached_at)
            })
            
        return Response({
            "success": True,
            "meta": {"total": len(data), "page": 1, "limit": len(data)},
            "data": data
        })


class ClaimPickupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, requestId, *args, **kwargs):
        user = request.user
        if user.role not in ['COLLECTOR_DRIVER', 'COLLECTOR_ADMIN']:
            return Response({"success": False, "message": "Unauthorized."}, status=403)
            
        pickup = get_object_or_404(PickupRequest, id=requestId)
        
        if pickup.cluster != user.cluster:
            return Response({"success": False, "message": "Pickup is outside your locked cluster."}, status=403)
            
        if pickup.status != PickupStatus.PENDING:
            return Response({"success": False, "message": "Pickup already claimed or not pending."}, status=400)
            
        pickup.status = PickupStatus.ASSIGNED
        pickup.assigned_collector = user
        pickup.save()
        
        return Response({
            "success": True,
            "message": "Request successfully claimed.",
            "data": {
                "requestId": pickup.id,
                "status": pickup.status,
                "assignedCollectorId": user.id
            }
        })


# ==============================================================================
# 3. PAYMENTS & FINANCIAL WITHDRAWALS VIEWS
# ==============================================================================

class InitializePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitializeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        callback_url = serializer.validated_data.get('callback_url', 'https://kole.com.ng/payment-complete')
        reference = f"KOLE-{uuid.uuid4().hex[:10].upper()}"

        paystack = PaystackService()
        res = paystack.initialize_transaction(
            email=request.user.email,
            amount_in_naira=amount,
            reference=reference,
            callback_url=callback_url
        )

        if res.get('status'):
            return Response({
                'success': True,
                'authorization_url': res['data']['authorization_url'],
                'access_code': res['data']['access_code'],
                'reference': reference
            }, status=status.HTTP_200_OK)
            
        return Response({'success': False, 'message': res.get('message', 'Payment initialization failed')}, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reference = serializer.validated_data['reference']
        paystack = PaystackService()
        res = paystack.verify_transaction(reference)

        if res.get('status') and res['data']['status'] == 'success':
            return Response({
                'success': True,
                'message': 'Payment successful',
                'data': res['data']
            }, status=status.HTTP_200_OK)

        return Response({'success': False, 'message': 'Transaction verification failed'}, status=status.HTTP_400_BAD_REQUEST)


class RequestWithdrawalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.role not in ['COLLECTOR_DRIVER', 'COLLECTOR_ADMIN'] or not hasattr(user, 'wallet'):
            return Response({"success": False, "message": "Unauthorized or no wallet available."}, status=403)
            
        amount = request.data.get('amount')
        
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return Response({"success": False, "message": "Invalid amount."}, status=400)
            
        wallet = user.wallet
        if wallet.balance < amount:
            return Response({"success": False, "message": "Insufficient balance."}, status=400)
            
        with transaction.atomic():
            wallet.balance -= amount
            wallet.save()
            
            entry = LedgerEntry.objects.create(
                reference=f"TX-LEDGER-{str(uuid.uuid4())[:8]}",
                wallet=wallet,
                type=TransactionType.DISPATCH_PAYOUT,
                status=TransactionStatus.PROCESSING,
                amount=-amount,
                description="Payout withdrawal request"
            )
            
        return Response({
            "success": True,
            "data": {
                "transactionRef": entry.reference,
                "amount": amount,
                "status": entry.status,
                "estimatedSettlement": "5-10 minutes"
            }
        })


# ==============================================================================
# 4. COMMERCIAL STAGING BAY VIEWS
# ==============================================================================

class OrganizationStagingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile, created = OrganizationProfile.objects.get_or_create(user=request.user)
        serializer = OrganizationProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class EvacuationScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            org_profile = request.user.organization_profile
        except OrganizationProfile.DoesNotExist:
            return Response({"success": False, "message": "Organization profile required first."}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['organization'] = org_profile.id
        serializer = EvacuationScheduleSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"success": True, "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# 5. WAITLIST & HEATMAP ANALYTICS VIEWS
# ==============================================================================

class WaitlistCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = WaitlistSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"success": True, "message": "Successfully joined the coverage waitlist!"}, status=status.HTTP_201_CREATED)
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class AdminHeatmapView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        heatmap_data = (
            WaitlistEntry.objects.values('area_name')
            .annotate(request_count=Count('id'))
            .order_by('-request_count')
        )
        return Response({"success": True, "data": list(heatmap_data)}, status=status.HTTP_200_OK)


# ==============================================================================
# 6. ADMIN DASHBOARD METRICS & SETTLEMENTS VIEWS
# ==============================================================================

class AdminMetricsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        gross_rev = LedgerEntry.objects.filter(status=TransactionStatus.SUCCESSFUL).aggregate(total=Sum('amount'))['total'] or 0.00
        active_pickups = PickupRequest.objects.filter(
            status__in=[PickupStatus.PENDING, PickupStatus.ASSIGNED, PickupStatus.IN_TRANSIT]
        ).count()
        completed_pickups = PickupRequest.objects.filter(status=PickupStatus.COMPLETED).count()
        est_tonnage = completed_pickups * 0.25  # ~0.25 tons per standard bin pickup

        return Response({
            "success": True,
            "data": {
                "gross_revenue": float(gross_rev),
                "tonnage_cleared": float(est_tonnage),
                "active_pickups_count": active_pickups,
                "completed_pickups_count": completed_pickups
            }
        }, status=status.HTTP_200_OK)


class SettlementListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        ledger_entries = LedgerEntry.objects.filter(pickup_request__isnull=False)
        serializer = SettlementOverviewSerializer(ledger_entries, many=True)
        return Response({
            "success": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)