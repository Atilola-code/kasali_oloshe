import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from decimal import Decimal

from .models import Expense
from .serializers import ExpenseSerializer, ExpenseStatsSerializer
from user.permissions import IsAdminOrManager

logger = logging.getLogger(__name__)


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing expenses
    """
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]
    
    def get_queryset(self):
        """
        Filter out deleted expenses
        """
        queryset = Expense.objects.filter(is_deleted=False).select_related(
            'created_by', 'updated_by'
        )
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('-date')
    
    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by to current user"""
        serializer.save(updated_by=self.request.user)
    
    @extend_schema(
        summary="Delete expense (soft delete)",
        description="Soft delete an expense record"
    )
    def destroy(self, request, *args, **kwargs):
        """Soft delete expense"""
        expense = self.get_object()
        expense.soft_delete(request.user)
        return Response(
            {'message': 'Expense deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @extend_schema(
        summary="Get expense statistics",
        description="Get expense statistics including totals and breakdowns"
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get expense statistics"""
        queryset = self.get_queryset()
        
        # Total expenses
        total_data = queryset.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # By category
        by_category = {}
        for category in dict(Expense.CATEGORY_CHOICES).keys():
            cat_total = queryset.filter(category=category).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            by_category[category] = float(cat_total)
        
        # By month (last 6 months)
        by_month = []
        for i in range(6):
            month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            
            month_total = queryset.filter(
                date__gte=month_start,
                date__lt=month_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            by_month.append({
                'month': month_start.strftime('%B %Y'),
                'total': float(month_total)
            })
        
        # Recent expenses
        recent = queryset[:10]
        
        data = {
            'total_expenses': total_data['total'] or Decimal('0.00'),
            'total_count': total_data['count'],
            'by_category': by_category,
            'by_month': by_month,
            'recent_expenses': ExpenseSerializer(recent, many=True).data
        }
        
        return Response(data)