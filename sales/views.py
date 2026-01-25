# sales/views.py
import logging
import traceback
from rest_framework import viewsets, generics, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone

from .models import Sale, Deposit, StopSaleLog, Credit, CreditPayment
from .serializers import SaleSerializer, DepositSerializer, StopSaleLogSerializer, StopSaleStatusSerializer, CreditSerializer, ClearCreditSerializer
from user.permissions import IsAdminOrManager, IsCashier

logger = logging.getLogger(__name__)

class SaleViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """
    Sale ViewSet that provides list, retrieve, create, update operations
    and custom actions for print count.
    """
    queryset = Sale.objects.all().order_by('-date')
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Optionally filter sales by date range
        """
        queryset = super().get_queryset()
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        return queryset


    @extend_schema(
        summary="List sales",
        description="Get a list of all sales with optional date filtering",
        parameters=[
            OpenApiParameter(
                name='start_date',
                description='Filter sales from this date (YYYY-MM-DD)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='end_date',
                description='Filter sales up to this date (YYYY-MM-DD)',
                required=False,
                type=str
            )
        ],
        tags=["Sales"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Create a new sale",
        description="Create a new sale and update inventory stock automatically",
        request=SaleSerializer,
        responses={201: SaleSerializer},
        tags=["Sales"]
    )
    def create(self, request, *args, **kwargs):
        """
        Override create to check if sales are stopped
        """
        try:
        # Check if sales are stopped
            is_stopped = cache.get('is_sale_stopped', False)
            
            if is_stopped:
                # Check if user is ADMIN or MANAGER
                user_role = request.user.role if hasattr(request.user, 'role') else None
                if user_role not in ['ADMIN', 'MANAGER']:
                    return Response(
                        {'error': 'Sales have been stopped by management. Please contact your supervisor.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            response = super().create(request, *args, **kwargs)
            logger.info(f"✅ Sale created successfully: {response.data.get('invoice_id')}")
            return response
                
        except Exception as e:
            logger.error(f"❌ Error creating sale: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {
                    'error': 'Failed to create sale',
                    'detail': str(e),
                    'type': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Update a sale",
        description="Update an existing sale",
        request=SaleSerializer,
        responses={200: SaleSerializer},
        tags=["Sales"]
    )
    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Error updating sale: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {
                    'error': 'Failed to update sale',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Increment receipt print count",
        description="Increment the receipt print count for a sale by 1",
        methods=["PATCH"],
        responses={200: {"receipt_print_count": "int"}},
        tags=["Sales"]
    )
    @action(detail=True, methods=['patch'])
    def increment_print_count(self, request, pk=None):
        try:
            sale = self.get_object()
            sale.increment_print_count()
            return Response({
                'receipt_print_count': sale.receipt_print_count,
                'message': 'Print count updated successfully'
            })
        except Exception as e:
            logger.error(f"❌ Error incrementing print count: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkSalesSyncView(generics.CreateAPIView):
    """
    Accepts many sales from offline client. Payload: {"sales": [ {...}, {...} ]}
    Each sale will update inventory and return created invoice IDs.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SaleSerializer

    def post(self, request, *args, **kwargs):
        try:
        # Check if sales are stopped
            is_stopped = cache.get('is_sale_stopped', False)
            
            if is_stopped:
                # Check if user is ADMIN or MANAGER
                user_role = request.user.role if hasattr(request.user, 'role') else None
                if user_role not in ['ADMIN', 'MANAGER']:
                    return Response(
                        {'error': 'Sales have been stopped. Cannot sync offline sales.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            sales_data = request.data.get("sales", [])
            created_invoices = []
            errors = []

            for sale_data in sales_data:
                serializer = SaleSerializer(data=sale_data, context={'request': request})
                if serializer.is_valid():
                    try:
                        with transaction.atomic():
                            sale = serializer.save()
                            created_invoices.append(sale.invoice_id)
                    except Exception as e:
                        logger.error(f"Failed to create sale in bulk sync: {str(e)}")
                        errors.append({f"sale_error": str(e)})
                        
                else:
                    errors.append(serializer.errors)

            return Response(
                {"created": created_invoices, "errors": errors},
                status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"❌ Error in bulk sales sync: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
class DepositAPIView(generics.ListCreateAPIView):  # Changed from APIView
    """
    Handle deposits with GET and POST methods
    """
    queryset = Deposit.objects.all().order_by('-date')
    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @extend_schema(
        summary="List deposits",
        description="Get a list of all deposits",
        tags=["Deposits"]
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create a new deposit",
        description="Create a new deposit record",
        request=DepositSerializer,
        responses={201: DepositSerializer},
        tags=["Deposits"]
    )
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

@extend_schema(
    tags=["Stop Sale"],
    summary="Get stop sale status",
    description="Check if sales are currently stopped and who stopped them",
    responses={200: StopSaleStatusSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stop_sale_status(request):
    """
    Get current stop sale status
    """
    is_stopped = cache.get('is_sale_stopped', False)
    
    # Get the latest stop log
    last_log = StopSaleLog.objects.filter(is_stopped=is_stopped).order_by('-created_at').first()
    
    # Check if current user can resume
    can_resume = request.user.role in ['ADMIN', 'MANAGER'] if hasattr(request.user, 'role') else False
    
    response_data = {
        'is_sale_stopped': is_stopped,
        'stopped_by': last_log.stopped_by.username if last_log and last_log.stopped_by else None,
        'stopped_at': last_log.stopped_at if last_log else None,
        'reason': last_log.reason if last_log else None,
        'can_resume': can_resume
    }
    
    serializer = StopSaleStatusSerializer(response_data)
    return Response(serializer.data)


@extend_schema(
    tags=["Stop Sale"],
    summary="Toggle stop sale",
    description="Stop or resume sales (Admin/Manager only)",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'action': {
                    'type': 'string',
                    'enum': ['stop', 'resume'],
                    'description': 'Action to perform'
                },
                'reason': {
                    'type': 'string',
                    'description': 'Reason for stopping sales (optional)'
                }
            },
            'required': ['action']
        }
    },
    responses={
        200: StopSaleStatusSerializer,
        403: {'description': 'Permission denied'},
        400: {'description': 'Invalid action'}
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_stop_sale(request):
    """
    Toggle stop sale status
    Only Admin or Manager can perform this action
    """
    # Check permission
    if request.user.role not in ['ADMIN', 'MANAGER']:
        return Response(
            {'error': 'Only administrators and managers can stop sales'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    action = request.data.get('action', '').lower()
    reason = request.data.get('reason', '')
    
    if action not in ['stop', 'resume']:
        return Response(
            {'error': 'Invalid action. Use "stop" or "resume"'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    current_status = cache.get('is_sale_stopped', False)
    
    if action == 'stop' and not current_status:
        # Stop sales
        stop_log = StopSaleLog.objects.create(
            is_stopped=True,
            stopped_by=request.user,
            stopped_at=timezone.now(),
            reason=reason
        )
        cache.set('is_sale_stopped', True, timeout=None)  # No expiration until resumed
        
        return Response({
            'is_sale_stopped': True,
            'stopped_by': request.user.username,
            'stopped_at': stop_log.stopped_at,
            'reason': reason,
            'message': 'Sales have been stopped successfully'
        }, status=status.HTTP_200_OK)
    
    elif action == 'resume' and current_status:
        # Resume sales
        # Get the active stop log
        active_log = StopSaleLog.objects.filter(is_stopped=True).order_by('-created_at').first()
        if active_log:
            active_log.is_stopped = False
            active_log.resumed_by = request.user
            active_log.resumed_at = timezone.now()
            active_log.save()
        
        cache.set('is_sale_stopped', False, timeout=None)
        
        return Response({
            'is_sale_stopped': False,
            'resumed_by': request.user.username,
            'resumed_at': timezone.now(),
            'message': 'Sales have been resumed successfully'
        }, status=status.HTTP_200_OK)
    
    else:
        return Response({
            'error': f'Sales are already {"stopped" if current_status else "active"}'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Stop Sale"],
    summary="Check if user can create sale",
    description="Check if the current user is allowed to create a sale",
    responses={200: {
        'type': 'object',
        'properties': {
            'can_create_sale': {'type': 'boolean'},
            'is_sale_stopped': {'type': 'boolean'},
            'user_role': {'type': 'string', 'nullable': True}
        }
    }}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_can_create_sale(request):
    """
    Check if the current user can create a sale
    """
    is_stopped = cache.get('is_sale_stopped', False)
    
    if not is_stopped:
        can_create = True
    else:
        # If sales are stopped, only ADMIN and MANAGER can create sales
        can_create = request.user.role in ['ADMIN', 'MANAGER'] if hasattr(request.user, 'role') else False
    
    return Response({
        'can_create_sale': can_create,
        'is_sale_stopped': is_stopped,
        'user_role': request.user.role if hasattr(request.user, 'role') else None
    })


@extend_schema(
    tags=["Stop Sale"],
    summary="Get stop sale history",
    description="Get history of all stop/resume actions (Admin/Manager only)"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stop_sale_history(request):
    """
    Get history of stop sale actions
    Only accessible by ADMIN and MANAGER
    """
    if request.user.role not in ['ADMIN', 'MANAGER']:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    logs = StopSaleLog.objects.all().order_by('-created_at')
    serializer = StopSaleLogSerializer(logs, many=True)
    return Response(serializer.data)


class DailySalesReportView(generics.GenericAPIView):  # Changed from APIView
    """
    Get daily sales report including deposits
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SaleSerializer  # Add this
    
    @extend_schema(
        tags=["Reports"],
        summary="Get daily sales report",
        description="Get sales and deposits grouped by date",
        parameters=[
            OpenApiParameter(
                name='start_date',
                description='Start date (YYYY-MM-DD)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='end_date',
                description='End date (YYYY-MM-DD)',
                required=False,
                type=str
            )
        ],
        responses={200: {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'date': {'type': 'string', 'format': 'date'},
                    'total_sales': {'type': 'number'},
                    'total_deposits': {'type': 'number'},
                    'cash_sales': {'type': 'number'},
                    'digital_sales': {'type': 'number'},
                    'credit_sales': {'type': 'number'},
                }
            }
        }}
    )
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Get sales
        sales_qs = Sale.objects.all()
        if start_date:
            sales_qs = sales_qs.filter(date__date__gte=start_date)
        if end_date:
            sales_qs = sales_qs.filter(date__date__lte=end_date)
        
        # Get deposits
        deposits_qs = Deposit.objects.all()
        if start_date:
            deposits_qs = deposits_qs.filter(date__date__gte=start_date)
        if end_date:
            deposits_qs = deposits_qs.filter(date__date__lte=end_date)
        
        # Group sales by date
        sales_by_date = {}
        for sale in sales_qs:
            date_str = sale.date.date().isoformat()
            if date_str not in sales_by_date:
                sales_by_date[date_str] = {
                    'date': sale.date.date(),
                    'sales': [],
                    'deposits': [],
                    'total_sales': 0,
                    'total_deposits': 0,
                    'cash_sales': 0,
                    'digital_sales': 0,
                    'credit_sales': 0
                }
            
            sales_by_date[date_str]['sales'].append({
                'invoice_id': sale.invoice_id,
                'customer_name': sale.customer_name,
                'amount': float(sale.total_amount),
                'payment_method': sale.payment_method,
                'date': sale.date,
                'type': 'sale'
            })
            
            sales_by_date[date_str]['total_sales'] += float(sale.total_amount)
            
            # Categorize by payment method
            if sale.payment_method == 'cash':
                sales_by_date[date_str]['cash_sales'] += float(sale.total_amount)
            elif sale.payment_method in ['transfer', 'pos']:
                sales_by_date[date_str]['digital_sales'] += float(sale.total_amount)
            elif sale.payment_method == 'credit':
                sales_by_date[date_str]['credit_sales'] += float(sale.total_amount)
        
        # Add deposits to dates
        for deposit in deposits_qs:
            date_str = deposit.date.date().isoformat()
            if date_str not in sales_by_date:
                sales_by_date[date_str] = {
                    'date': deposit.date.date(),
                    'sales': [],
                    'deposits': [],
                    'total_sales': 0,
                    'total_deposits': 0,
                    'cash_sales': 0,
                    'digital_sales': 0,
                    'credit_sales': 0
                }
            
            sales_by_date[date_str]['deposits'].append({
                'id': deposit.id,
                'depositor_name': deposit.depositor_name,
                'bank_name': deposit.bank_name,
                'amount': float(deposit.amount),
                'date': deposit.date,
                'type': 'deposit'
            })
            
            sales_by_date[date_str]['total_deposits'] += float(deposit.amount)
        
        # Convert to list and sort by date descending
        result = list(sales_by_date.values())
        result.sort(key=lambda x: x['date'], reverse=True)
        
        return Response(result)

class CreditViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing credits
    """
    queryset = Credit.objects.all().order_by('-date')
    serializer_class = CreditSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Optionally filter by status
        """
        queryset = super().get_queryset()
        status = self.request.query_params.get('status')
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    @extend_schema(
        summary="Clear credit",
        description="Record a payment to clear or partially clear a credit",
        request=ClearCreditSerializer,
        responses={200: CreditSerializer}
    )
    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        """
        Clear or partially clear a credit
        """
        credit = self.get_object()

        if credit.status == 'cleared':
            return Response(
                {'error': 'Credit is already cleared'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ClearCreditSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        amount_paid = serializer.validated_data['amount_paid']
        
        # Validate amount
        if amount_paid > credit.outstanding_amount:
            return Response(
                {'error': f'Payment amount cannot exceed outstanding amount ({credit.outstanding_amount})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment record
        with transaction.atomic():
            payment = CreditPayment.objects.create(
            credit=credit,
            amount=amount_paid,
            customer_name=serializer.validated_data['customer_name'],
            payment_method=serializer.validated_data['payment_method'],
            remarks=serializer.validated_data.get('remarks', ''),
            recorded_by=request.user
        )
            
        # If digital payment, create deposit automatically
        if payment.payment_method in ['transfer', 'pos', 'bank']:
            Deposit.objects.create(
                amount=amount_paid,
                depositor_name=payment.customer_name,
                bank_name=f"Credit Payment - {credit.invoice_id}",
                created_by=request.user
            )

        # Return updated credit
        credit.refresh_from_db()
        response_serializer = CreditSerializer(credit)
        return Response(response_serializer.data)
    
    @extend_schema(
        summary="Mark as partially paid",
        description="Mark a credit as partially paid without recording payment",
        responses={200: CreditSerializer}
    )
    
    @action(detail=True, methods=['post'])
    def mark_partial(self, request, pk=None):
        """
        Mark a credit as partially paid
        """
        credit = self.get_object()
        
        if credit.status == 'cleared':
            return Response(
                {'error': 'Credit is already cleared'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if credit.status != 'partially_paid':
            credit.status = 'partially_paid'
            credit.save(update_fields=['status'])
        
        credit.refresh_from_db()
        response_serializer = CreditSerializer(credit)
        return Response(response_serializer.data)