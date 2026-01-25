# purchase_orders/views.py
from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db import transaction
from django.utils import timezone
import traceback
import logging

from .models import PurchaseOrder, PurchaseOrderHistory
from .serializers import PurchaseOrderSerializer, ChangeStatusSerializer
from user.permissions import IsAdminOrManager

logger = logging.getLogger(__name__)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing purchase orders
    """
    queryset = PurchaseOrder.objects.all().prefetch_related('items', 'history')
    serializer_class = PurchaseOrderSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['po_number', 'supplier_name', 'status']
    ordering_fields = ['order_date', 'expected_delivery', 'total_amount', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Optionally filter by status
        """
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @extend_schema(
        summary="List all purchase orders",
        description="Get a list of all purchase orders with optional filtering",
        tags=["Purchase Orders"]
    )
    def list(self, request, *args, **kwargs):
        """
        FIXED: Return consistent response structure
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            
            logger.info(f"📦 Returning {len(serializer.data)} purchase orders")
            
            # Return data in expected format
            return Response({
                'count': queryset.count(),
                'result': serializer.data  # Changed from 'results' to 'result'
            })
        except Exception as e:
            logger.error(f"❌ Error listing POs: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e), 'result': []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Create a new purchase order",
        description="Create a new purchase order with items",
        request=PurchaseOrderSerializer,
        responses={201: PurchaseOrderSerializer},
        tags=["Purchase Orders"]
    )
    def create(self, request, *args, **kwargs):
        """
        FIXED: Better error handling for PO creation
        """
        try:
            logger.info(f"📝 Creating PO with data: {request.data}")
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            logger.info(f"✅ PO created: {serializer.data.get('po_number')}")
            
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED, 
                headers=headers
            )
        except Exception as e:
            logger.error(f"❌ Error creating PO: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {
                    'error': 'Failed to create purchase order',
                    'detail': str(e),
                    'type': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Retrieve purchase order details",
        description="Get detailed information about a specific purchase order",
        tags=["Purchase Orders"]
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Error retrieving PO: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Update purchase order",
        description="Update an existing purchase order",
        request=PurchaseOrderSerializer,
        responses={200: PurchaseOrderSerializer},
        tags=["Purchase Orders"]
    )
    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ Error updating PO: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Change purchase order status",
        description="Change the status of a purchase order (pending, approved, received, cancelled)",
        request=ChangeStatusSerializer,
        responses={200: PurchaseOrderSerializer},
        tags=["Purchase Orders"]
    )
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """
        Change the status of a purchase order
        """
        try:
            po = self.get_object()
            serializer = ChangeStatusSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            new_status = serializer.validated_data['status']
            notes = serializer.validated_data.get('notes', '')
            old_status = po.status
            
            # Validate status transitions
            valid_transitions = {
                'draft': ['pending', 'cancelled'],
                'pending': ['approved', 'cancelled'],
                'approved': ['received', 'cancelled'],
                'received': [],
                'cancelled': []
            }
            
            if new_status not in valid_transitions.get(old_status, []):
                return Response(
                    {'error': f'Cannot change status from {old_status} to {new_status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Update status
                po.status = new_status
                
                # Set timestamp and user based on status
                if new_status == 'approved':
                    po.approved_by = request.user
                    po.approved_at = timezone.now()
                elif new_status == 'received':
                    po.received_by = request.user
                    po.received_at = timezone.now()
                    
                    # Update inventory when PO is received
                    self._update_inventory(po)
                
                po.save()
                
                # Log status change
                PurchaseOrderHistory.objects.create(
                    purchase_order=po,
                    action=f'Status changed to {new_status}',
                    old_status=old_status,
                    new_status=new_status,
                    performed_by=request.user,
                    notes=notes or f'Status changed from {old_status} to {new_status}'
                )
            
            logger.info(f"✅ PO {po.po_number} status changed: {old_status} → {new_status}")
            
            # Return updated PO with all related data
            serializer = self.get_serializer(po)
            return Response(serializer.data)
        
        except Exception as e:
            logger.error(f"❌ Error changing PO status: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _update_inventory(self, po):
        """
        Update inventory quantities when PO is received
        """
        from inventory.models import Product
        
        for item in po.items.all():
            product = item.product
            product.quantity += item.quantity
            product._updated_by = po.received_by
            product._update_reason = f'Purchase Order {po.po_number} received'
            product.save()
            logger.info(f"📦 Updated {product.name} quantity: +{item.quantity}")
    
    @extend_schema(
        summary="Get purchase order statistics",
        description="Get statistics about purchase orders",
        tags=["Purchase Orders"]
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get PO statistics
        """
        try:
            from django.db.models import Sum, Count, Q
            
            total_pos = PurchaseOrder.objects.count()
            draft_count = PurchaseOrder.objects.filter(status='draft').count()
            pending_count = PurchaseOrder.objects.filter(status='pending').count()
            approved_count = PurchaseOrder.objects.filter(status='approved').count()
            received_count = PurchaseOrder.objects.filter(status='received').count()
            
            total_value = PurchaseOrder.objects.filter(
                status__in=['approved', 'received']
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            pending_value = PurchaseOrder.objects.filter(
                status='pending'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            logger.info(f"📊 Statistics: {total_pos} total POs")
            
            return Response({
                'total_purchase_orders': total_pos,
                'draft': draft_count,
                'pending': pending_count,
                'approved': approved_count,
                'received': received_count,
                'total_value': float(total_value),
                'pending_value': float(pending_value)
            })
        except Exception as e:
            logger.error(f"❌ Error fetching statistics: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )