from os import times

import requests
from django.db.models.expressions import result
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Transaction
import base64
from datetime import datetime
import json
from django.core.mail import send_mail
from django.core.paginator import Paginator
from .utility import CONSUMER_KEY,CONSUMER_SECRET,BASE_URL,SHORTCODE,PASSKEY,NGROK_URL
# Create your views here.

# helper class for transaction security credential generation
class MpesaPassword:
    @staticmethod
    def generate_security_credential():
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_to_encode = SHORTCODE + PASSKEY + timestamp
        online_password = base64.b64encode(data_to_encode.encode()).decode()

        return online_password


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
        print("access token " , access_token)
        stk_url = f'{BASE_URL}/mpesa/stkpush/v1/processrequest'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(f'{SHORTCODE}{PASSKEY}{timestamp}'.encode()).decode()
        print(stk_url)
        print(password)
        print(timestamp)

        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": SHORTCODE,
            "PhoneNumber" : phone,
            "CallBackURL": "https://stkpushmpesa.onrender.com/callback",
            "AccountReference": f"Transaction_{transaction.id}",
            "TransactionDesc": "Payment for Services"
        }

        response = requests.post(stk_url, json=payload, headers=headers)
        print("response" , response)
        response_data = response.json()

        print(response_data)

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
# this function maps the callback url that will receive the result body of a payment attempt
@csrf_exempt
def callback(request):
    if request.method == 'POST':
        try:
            # response from  daraja api upon payment attempt
            data = json.loads(request.body)
            print("received callback data " , data)
            stk_callback = data.get('Body',{}).get('stkCallback',{})
            result_code = stk_callback.get('ResultCode',None)
            result_desc = stk_callback.get('ResultDesc','')
            transaction_id = stk_callback.get('CheckoutRequestID',None)
            print(transaction_id,result_code)

            if transaction_id:
                transaction = Transaction.objects.filter(transaction_id=transaction_id).first()
                print("my transaction in db ", transaction)
                if transaction:
                    if result_code == 0:
                        callback_metadata = stk_callback.get('CallbackMetadata',{}).get('Item',[])
                        receipt_number = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'MpesaReceiptNumber'), None)
                        amount = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'Amount'), None)
                        transaction_date_str = next((item.get('Value') for item in callback_metadata if item.get('Name') == 'TransactionDate'), None)
                        # cleaning our transaction date screen
                        transaction_date = None
                        if transaction_date_str:
                            transaction_date = datetime.strptime(str(transaction_date_str), '%Y%m%d%H%M%S')

                        # updating transaction fields
                        transaction.mpesa_receipt_number = receipt_number
                        transaction.transaction_date = transaction_date
                        transaction.amount = amount
                        transaction.status = "Success"
                        transaction.description = "Payment Successful"
                        transaction.save()
                        print(f"Transaction {transaction_id} - {transaction.status} updated successfully")

                        ## TODO :  SEND EMAIL
                        if transaction.email:
                            subject = "Payment Receipt Confirmation"
                            message = (
                                f"Dear {transaction.name}, \n\n"
                                f"Thank you for your payment of {transaction.amount}"
                                f"Your MPESA confirmation receipt is {transaction.mpesa_receipt_number}"
                                "Best Regards , \n"
                                "STK PUSH"
                            )
                            html_message = (
                                f"<p>Dear {transaction.name},</p>"
                                f"<p>Thank you for your payment of {transaction.amount}</p>"
                                f"<p>Your MPESA confirmation receipt is {transaction.mpesa_receipt_number}</p>"
                                f"<p>Best Regards, STK Push</p>"
                            )
                            send_mail(subject,message,'josephbill00@gmail.com',[transaction.email]
                                      ,fail_silently=False,html_message=html_message,)
                            print("Payment receipt email sent successfully")

                    elif result_code == 1:
                        transaction.status = "Failed"
                        transaction.description = result_desc
                        transaction.save()
                        print(f"Transaction {transaction_id} - {result_desc} failed.")
                    elif result_code == 1032:
                        transaction.status = "Cancelled"
                        transaction.description = "Transaction Cancelled by User"
                        transaction.save()
                        print(f"Transaction {transaction_id} marked as cancelled.")

            return JsonResponse({"message": "callback received and processed"}, status=200)

        except Exception as e:
            print(f"Error processing callback {e}")
            return JsonResponse({"error": f"Error processing callback {e}"}, status=500)

    return JsonResponse({"error" : "Invalid request method"}, status=400)

def check_status(request, transaction_id):
    # get the transaction needed for the process
    transaction = Transaction.objects.filter(id=transaction_id).first()
    if not transaction:
        return JsonResponse({"status": "failed" , "message": "Transaction not found"}, status=400)

    '''
    on stk prompt the transaction status is pending 
    on successful payments the transaction status is success 
    on failure the transaction status is failed 
    on cancellation the transaction status is canceled
    '''

    if transaction.status == "Success":
        return JsonResponse({"status": "Success", "message": "Payment Successful"}, status=200)
    elif transaction.status == "Failed":
        return JsonResponse({"status": "Failed", "message": "Payment Failed"}, status=200)
    elif transaction.status == "Cancelled":
        return JsonResponse({"status": "Cancelled", "message": "Transaction was Cancelled"}, status=200)
    else:
        return JsonResponse({"status": "Pending", "message": "Transaction still being processed."}, status=400)


def payment_success(request):
    return render(request,"payment_success.html")

def payment_failed(request):
    return render(request,"payment_failed.html")

def payment_cancelled(request):
    return render(request,"payment_cancelled.html")




















