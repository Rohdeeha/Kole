import logging
import uuid
from datetime import timedelta
from decimal import Decimal
import requests
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.db.models import Sum, Count

from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    PickupRequest, PickupStatus, Wallet, LedgerEntry, 
    TransactionType, TransactionStatus, WaitlistEntry, 
    OrganizationProfile, EvacuationSchedule, UserRole,
    AccountStatus, Cluster, CollectorProfile
)
from .serializers import (
    RegistrationSerializer, CustomTokenObtainPairSerializer, GoogleAuthSerializer,
    PickupRequestSerializer, CreatePickupRequestSerializer, QuoteSerializer,
    UpdateLocationSerializer, SubaccountSetupSerializer, UserSerializer,
    WaitlistSerializer, OrganizationProfileSerializer, 
    EvacuationScheduleSerializer, SettlementOverviewSerializer,
    PaymentInitializeSerializer, PaymentVerifySerializer
)
from .paystack import PaystackService

logger = logging.getLogger(__name__)
User = get_user_model()


def verify_google_credential(credential: str):
    """
    Verifies a Google OAuth ID token using the google-auth library if available,
    with an HTTP fallback to Google's tokeninfo endpoint.
    """
    # Attempt 1: google-auth library
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        idinfo = id_token.verify_oauth2_token(credential, google_requests.Request())
        return idinfo
    except Exception as e:
        logger.debug(f"google.oauth2 verification error: {e}, attempting HTTP tokeninfo fallback.")

    # Attempt 2: Direct HTTP tokeninfo
    try:
        res = requests.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        logger.error(f"Google tokeninfo HTTP error: {e}")

    return None


# ==============================================================================
# 1. AUTHENTICATION & ONBOARDING VIEWS
# ==============================================================================

class RegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "success": True,
            "message": "User registered successfully.",
            "accessToken": str(refresh.access_token),
            "refreshToken": str(refresh),
            "user": UserSerializer(user).data,
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


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data['credential']
        target_role = serializer.validated_data.get('role', UserRole.RESIDENT)

        google_user = verify_google_credential(credential)
        if not google_user or 'email' not in google_user:
            return Response({
                "success": False,
                "message": "Invalid or expired Google credential."
            }, status=status.HTTP_400_BAD_REQUEST)

        email = google_user['email'].lower().strip()
        first_name = google_user.get('given_name') or google_user.get('name') or ''
        last_name = google_user.get('family_name') or ''

        user = User.objects.filter(email=email).first()
        if not user:
            # Create user
            username = email
            user = User.objects.create(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=target_role,
                status=AccountStatus.ACTIVE,
                is_active=True
            )
            user.set_unusable_password()
            user.save()
            Wallet.objects.get_or_create(user=user)

            if target_role == UserRole.ORGANIZATION:
                OrganizationProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'facility_name': f"{first_name}'s Facility",
                        'officer_in_charge': f"{first_name} {last_name}".strip()
                    }
                )
            elif target_role in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN]:
                CollectorProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization_name': f"{first_name} Waste Operations",
                        'operating_license_num': f"GOOG-{user.id.hex[:8].upper()}"
                    }
                )

        refresh = RefreshToken.for_user(user)
        return Response({
            "success": True,
            "message": "Google authentication successful.",
            "accessToken": str(refresh.access_token),
            "refreshToken": str(refresh),
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


# ==============================================================================
# 2. PICKUP REQUESTS & DISPATCH OPERATIONS
# ==============================================================================

class PickupsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        user = request.user
        queryset = PickupRequest.objects.all()

        # Role-based segmentation
        if user.role == UserRole.RESIDENT:
            queryset = queryset.filter(resident=user)
        elif user.role in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN]:
            # Collectors see cluster requests or assigned requests
            if user.cluster:
                queryset = queryset.filter(models.Q(cluster=user.cluster) | models.Q(assigned_collector=user))
            else:
                queryset = queryset.filter(assigned_collector=user)

        # Filters
        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status__iexact=status_param)

        emergency_param = request.query_params.get('is_emergency')
        if emergency_param is not None:
            is_em = str(emergency_param).lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_emergency=is_em)

        cluster_param = request.query_params.get('cluster')
        if cluster_param:
            queryset = queryset.filter(cluster_id=cluster_param)

        serializer = PickupRequestSerializer(queryset, many=True)
        return Response({
            "success": True,
            "data": serializer.data,
            "meta": {"total": queryset.count()}
        }, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        serializer = CreatePickupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Target cluster resolution
        cluster_id = serializer.validated_data.get('cluster')
        target_cluster = None
        if cluster_id:
            target_cluster = Cluster.objects.filter(id=cluster_id).first()
        if not target_cluster:
            target_cluster = user.cluster
        if not target_cluster:
            target_cluster = Cluster.objects.first()

        if not target_cluster:
            return Response({
                "success": False,
                "message": "No active cluster found. Please select or join a cluster."
            }, status=status.HTTP_400_BAD_REQUEST)

        is_emergency = serializer.validated_data.get('is_emergency', False)
        now = timezone.now()
        sla_hours = 4 if is_emergency else 48
        sla_due_at = now + timedelta(hours=sla_hours)
        tracking_num = f"KOL-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        pickup = PickupRequest.objects.create(
            tracking_num=tracking_num,
            resident=user,
            cluster=target_cluster,
            pickup_address=serializer.validated_data['address'],
            latitude=serializer.validated_data.get('latitude', Decimal('7.7825')),
            longitude=serializer.validated_data.get('longitude', Decimal('4.5621')),
            waste_volume_est=serializer.validated_data.get('waste_volume_est', 'STANDARD_BIN'),
            fixed_service_fee=Decimal('0.00') if is_emergency else Decimal('1500.00'),
            is_emergency=is_emergency,
            status=PickupStatus.PENDING_QUOTE if is_emergency else PickupStatus.PENDING,
            sla_due_at=sla_due_at,
            proof_image=serializer.validated_data.get('proof_image')
        )

        return Response({
            "success": True,
            "message": "Pickup request created successfully.",
            "data": PickupRequestSerializer(pickup).data
        }, status=status.HTTP_201_CREATED)


class PickupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        pickup = get_object_or_404(PickupRequest, pk=pk)
        return Response({
            "success": True,
            "data": PickupRequestSerializer(pickup).data
        }, status=status.HTTP_200_OK)


class PickupQuoteView(APIView):
    """
    Allows registered collectors assigned to the cluster to submit a custom price quote,
    shifting the request status to QUOTED.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        pickup = get_object_or_404(PickupRequest, pk=pk)

        if user.role not in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN, UserRole.SYSTEM_ADMIN]:
            return Response({
                "success": False,
                "message": "Only registered waste collectors can submit quotes."
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = QuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        price = serializer.validated_data['price']

        pickup.quote_price = price
        pickup.fixed_service_fee = price
        pickup.status = PickupStatus.QUOTED
        pickup.assigned_collector = user
        pickup.save()

        return Response({
            "success": True,
            "message": f"Quote of ₦{price:,.2f} submitted successfully.",
            "data": PickupRequestSerializer(pickup).data
        }, status=status.HTTP_200_OK)


class PickupUpdateLocationView(APIView):
    """
    Updates collector coordinates in real-time and sets status to in_transit
    so households see tracking updates ("Almost There").
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        pickup = get_object_or_404(PickupRequest, pk=pk)

        if user.role not in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN, UserRole.SYSTEM_ADMIN]:
            return Response({"success": False, "message": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data['latitude']
        lng = serializer.validated_data['longitude']

        if hasattr(user, 'collector_profile'):
            profile = user.collector_profile
            profile.current_lat = lat
            profile.current_lng = lng
            profile.save(update_fields=['current_lat', 'current_lng', 'updated_at'])

        pickup.status = PickupStatus.IN_TRANSIT
        if not pickup.assigned_collector:
            pickup.assigned_collector = user
        pickup.save(update_fields=['status', 'assigned_collector', 'updated_at'])

        return Response({
            "success": True,
            "message": "Collector location updated; status shifted to in_transit.",
            "data": {
                "requestId": str(pickup.id),
                "status": pickup.status,
                "latitude": float(lat),
                "longitude": float(lng)
            }
        }, status=status.HTTP_200_OK)


class PickupCompleteView(APIView):
    """
    Allows the assigned collector to mark the job as completed,
    triggering cleanup and final settlement flows.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        pickup = get_object_or_404(PickupRequest, pk=pk)

        if user.role not in [UserRole.COLLECTOR_DRIVER, UserRole.COLLECTOR_ADMIN, UserRole.SYSTEM_ADMIN]:
            return Response({"success": False, "message": "Unauthorized."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            pickup.status = PickupStatus.COMPLETED
            pickup.completed_at = timezone.now()
            pickup.save()

            collector = pickup.assigned_collector or user
            total_amount = pickup.fixed_service_fee or pickup.quote_price or Decimal('1500.00')
            collector_share = total_amount * Decimal('0.80')
            platform_fee = total_amount * Decimal('0.20')

            collector_wallet, _ = Wallet.objects.get_or_create(user=collector)
            collector_wallet.balance += collector_share
            collector_wallet.save()

            LedgerEntry.objects.create(
                reference=f"SETTLE-{uuid.uuid4().hex[:10].upper()}",
                wallet=collector_wallet,
                pickup_request=pickup,
                type=TransactionType.DISPATCH_PAYOUT,
                status=TransactionStatus.SUCCESSFUL,
                amount=total_amount,
                collector_share=collector_share,
                platform_commission=platform_fee,
                description=f"Automated settlement for completed pickup {pickup.tracking_num}"
            )

        return Response({
            "success": True,
            "message": "Job marked as completed and automated settlement processed.",
            "data": PickupRequestSerializer(pickup).data
        }, status=status.HTTP_200_OK)


# Backward compatible endpoints
class RequestPickupView(PickupsView):
    pass


class CollectorQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role not in ['COLLECTOR_DRIVER', 'COLLECTOR_ADMIN'] or not user.cluster:
            return Response({"success": False, "message": "Unauthorized."}, status=403)
            
        requests = PickupRequest.objects.filter(
            cluster=user.cluster, 
            status__in=[PickupStatus.PENDING, PickupStatus.PENDING_QUOTE]
        )
        
        data = []
        for req in requests:
            data.append({
                "requestId": req.id,
                "trackingNum": req.tracking_num,
                "address": req.pickup_address,
                "status": req.status,
                "isEmergency": req.is_emergency,
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
            
        if pickup.status not in [PickupStatus.PENDING, PickupStatus.QUOTED]:
            return Response({"success": False, "message": "Pickup already claimed or not eligible."}, status=400)
            
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
# 3. FINANCE & SUBACCOUNTS
# ==============================================================================

class CollectorSubaccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not hasattr(user, 'collector_profile'):
            return Response({"success": False, "message": "User does not have a collector profile."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubaccountSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = user.collector_profile
        bank_code = serializer.validated_data['bank_code']
        account_number = serializer.validated_data['account_number']
        business_name = serializer.validated_data.get('business_name') or profile.organization_name or f"{user.first_name} Operations"
        account_name = serializer.validated_data.get('account_name', '')

        paystack = PaystackService()
        res = paystack.create_subaccount(
            business_name=business_name,
            settlement_bank=bank_code,
            account_number=account_number,
            percentage_charge=20.0,
            description=f"Kole split settlement subaccount for {business_name}"
        )

        if res.get('status') and 'data' in res:
            sub_code = res['data'].get('subaccount_code')
            profile.paystack_subaccount_code = sub_code
            profile.settlement_bank = res['data'].get('settlement_bank', bank_code)
            profile.bank_code = bank_code
            profile.account_number = account_number
            if account_name:
                profile.account_name = account_name
            profile.save()

            return Response({
                "success": True,
                "message": "Paystack subaccount created and stored successfully.",
                "subaccount_code": sub_code,
                "data": UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response({
            "success": False,
            "message": res.get('message', 'Failed to configure Paystack subaccount.')
        }, status=status.HTTP_400_BAD_REQUEST)


class BankListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        paystack = PaystackService()
        res = paystack.list_banks()
        return Response(res, status=status.HTTP_200_OK if res.get('status') else status.HTTP_400_BAD_REQUEST)


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
            wallet.balance -= Decimal(str(amount))
            wallet.save()
            
            entry = LedgerEntry.objects.create(
                reference=f"TX-LEDGER-{str(uuid.uuid4())[:8]}",
                wallet=wallet,
                type=TransactionType.DISPATCH_PAYOUT,
                status=TransactionStatus.PROCESSING,
                amount=-Decimal(str(amount)),
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
            entry = serializer.save()
            return Response({
                "success": True,
                "message": "Successfully joined the coverage waitlist!",
                "data": WaitlistSerializer(entry).data
            }, status=status.HTTP_201_CREATED)
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        entries = WaitlistEntry.objects.all()
        return Response({
            "success": True,
            "data": WaitlistSerializer(entries, many=True).data
        }, status=status.HTTP_200_OK)


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
            status__in=[PickupStatus.PENDING, PickupStatus.PENDING_QUOTE, PickupStatus.QUOTED, PickupStatus.ASSIGNED, PickupStatus.IN_TRANSIT]
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