from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'), #form page
    path('stk_push/', views.stk_push, name='stk_push'),
    path('waiting/<int:transaction_id>/', views.waiting_page, name='waiting_page'),
    path('callback', views.callback, name='callback'),
    path('check-status/<int:transaction_id>/', views.check_status, name='check-status'),
    path('payment-success/', views.payment_success, name='payment-success'),
    path('payment-failed/', views.payment_failed, name='payment-failed'),
    path('payment-cancelled/', views.payment_cancelled, name='payment-cancelled'),

]