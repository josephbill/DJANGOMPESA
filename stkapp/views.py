from os import times

import requests
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Transaction
import base64
from datetime import datetime
import json
from django.core.mail import send_mail
from django.core.paginator import Paginator
from .utility import CONSUMER_KEY,CONSUMER_SECRET,BASE_URL,SHORTCODE,PASSKEY
# Create your views here.
# get an access token
def generate_access_token():
    auth_url = f'{BASE_URL}/oauth/v1/generate?grant_type=client_credentials'
    response = requests.get(auth_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    return response.json().get('access_token')

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def stk_push(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')
        name = request.POST.get('name')
        email = request.POST.get('email')

        transaction = Transaction.objects.create(
            phone_number=phone,
            amount=amount,
            status="Pending",
            description="Awaiting status result",
            name=name,
            email=email,
        )

        access_token = generate_access_token()
        stk_url = f'{BASE_URL}/mpesa/stkpush/v1/processrequest'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f'{SHORTCODE}{PASSKEY}{timestamp}'.encode()).decode()

        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": "https://lucent-moxie-7b30b4.netlify.app/",
            "AccountReference": f"Transaction_{transaction.id}",
            "TransactionDesc": "Payment for Services"
        }

        response = requests.post(stk_url, json=payload, headers=headers)
        response_data = response.json()

        transaction_id = response_data.get('CheckoutRequestID', None)
        transaction.transaction_id = transaction_id
        transaction.description = response_data.get('ResponseDescription', "No Description")
        transaction.save()

        return redirect('waiting_page', transaction_id=transaction.id)
    return JsonResponse({'error': "invalid request"}, status=400)

def waiting_page(request, transaction_id):
    transaction = Transaction.objects.get(id=transaction_id)
    return render(request, 'waiting.html',{'transaction_id': transaction_id})


# TODO : IMPLEMENT CALLBACK PROCESS HERE i.e. GET RESULTS OF PAYMENT FROM THE REQUEST MADE ABOVE





















