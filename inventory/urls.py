from django.urls import path
from .views import ProductListCreateView, ProductRetrieveUpdateDestroyView, ProductSearchView, LowStockListView, ProductQuickSearchView

urlpatterns = [
    path('', ProductListCreateView.as_view(), name='product-list-create'),
    path('<int:pk>/', ProductRetrieveUpdateDestroyView.as_view(), name='product-detail'),
    path('search/', ProductSearchView.as_view(), name='product-search'),
    path('quick-search/', ProductQuickSearchView.as_view(), name='product-quick-search'),
    path('low-stock/', LowStockListView.as_view(), name='low-stock-list'),
]
