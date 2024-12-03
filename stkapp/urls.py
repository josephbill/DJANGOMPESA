from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'), #form page
    path('stk_push/', views.stk_push, name='stk_push'),
    path('waiting/<int:transaction_id>', views.waiting_page, name='waiting_page'),
    path('callback', views.callback, name='callback'),
    path('check-transaction/<str:transaction_id>', views.query_transaction, name='check-transaction'),

]