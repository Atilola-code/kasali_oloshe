# sales/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

credits_router = DefaultRouter()
credits_router.register(r'', views.CreditViewSet, basename='credit')

router = DefaultRouter()
router.register(r'', views.SaleViewSet, basename='sale')


urlpatterns = [
    #Credit endpoints
    path('credits/', include(credits_router.urls)),

    # Deposit endpoints
    path('deposits/', views.DepositAPIView.as_view(), name='deposit-list-create'),
    
    # Sales endpoints
    path('bulk-sync/', views.BulkSalesSyncView.as_view(), name='bulk-sync'),
    
    
    # Stop sale endpoints
    path('stop-sale/status/', views.get_stop_sale_status, name='stop-sale-status'),
    path('stop-sale/toggle/', views.toggle_stop_sale, name='toggle-stop-sale'),
    path('stop-sale/can-create/', views.check_can_create_sale, name='check-can-create-sale'),
    path('stop-sale/history/', views.get_stop_sale_history, name='stop-sale-history'),
    
    # Report endpoints
    path('daily-report/', views.DailySalesReportView.as_view(), name='daily-sales-report'),


    path('', include(router.urls)),
]