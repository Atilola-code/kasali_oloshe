from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db import models
from .models import Product
from .serializers import ProductSerializer, ProductReadOnlySerializer
from user.permissions import IsAdminOrManager 
from rest_framework.permissions import SAFE_METHODS

class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all().order_by('-date_added')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name','sku','category','supplier']

    def get_serializer_class(self):
        """Use different serializer based on user role"""
        if self.request.user.role in ['ADMIN', 'MANAGER']:
            return ProductSerializer
        return ProductReadOnlySerializer

    def get_permissions(self):
        """Override to allow cashiers to view but not create"""
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminOrManager()]

    @extend_schema(summary="List and Create Products", tags=["Inventory"])
    def get(self, request, *args, **kwargs):
        return super().get(request,*args,**kwargs)

    @extend_schema(request=ProductSerializer, responses={201: ProductSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request,*args,**kwargs)

class ProductRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Override to allow cashiers to view but not modify"""
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]  # Anyone authenticated can view
        return [IsAuthenticated(), IsAdminOrManager()]
    
    @extend_schema(summary="Retrieve, update or delete a product", tags=["Inventory"])
    def get(self, request, *args, **kwargs):
        return super().get(request,*args,**kwargs)


class ProductSearchView(generics.ListAPIView):
    """Search by name or SKU. Useful for scanning/lookup in sales UI."""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name','sku']
    pagination_class = None

    @extend_schema(summary="Search products by name or sku", tags=["Inventory"])
    def get(self, request, *args, **kwargs):
        return super().get(request,*args,**kwargs)


class LowStockListView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="List low-stock products", tags=["Inventory"])
    def get_queryset(self):
        return Product.objects.filter(quantity__lte=models.F('low_stock_threshold')).order_by('quantity')
    
class ProductQuickSearchView(generics.ListAPIView):
    """Quick search for product names/SKUs for sales"""
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if len(query) < 2:
            return Product.objects.none()
        
        return Product.objects.filter(
            models.Q(name__icontains=query) | 
            models.Q(sku__icontains=query)
        )[:10]
