import os
from dotenv import load_dotenv
import requests
import secrets
from datetime import datetime

from flask import url_for

load_dotenv()

# Paystack configuration
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = 'https://api.paystack.co'


class PaystackAPI:
    def __init__(self, secret_key):
        self.secret_key = secret_key
        self.headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_transaction(self, email, amount, reference=None):
        """Initialize a payment transaction"""
        url = f"{PAYSTACK_BASE_URL}/transaction/initialize"

        data = {
            "email": email,
            "amount": int(amount * 100),  # Amount in kobo
            "reference": reference or self.generate_reference(),
            "callback_url": url_for("payment_callback", _external=True)
        }

        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def verify_transaction(self, reference):
        """Verify a payment transaction"""
        url = f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def generate_reference(self):
        """Generate a unique transaction reference"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_string = secrets.token_hex(4)
        return f"TXN_{timestamp}_{random_string}"


