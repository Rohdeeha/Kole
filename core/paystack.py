import os
import requests
from django.conf import settings


class PaystackService:
    """Helper service class for Paystack API transactions."""

    def __init__(self):
        # Read the secret key from settings or environment variables
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', os.environ.get('PAYSTACK_SECRET_KEY'))
        self.base_url = 'https://api.paystack.co'
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }

    def initialize_transaction(self, email: str, amount_in_naira: float, reference: str, callback_url: str = None):
        """Initializes a payment transaction with Paystack."""
        url = f'{self.base_url}/transaction/initialize'
        
        # Paystack expects amounts in Kobo (1 Naira = 100 Kobo)
        amount_in_kobo = int(amount_in_naira * 100)

        payload = {
            'email': email,
            'amount': amount_in_kobo,
            'reference': reference,
        }

        if callback_url:
            payload['callback_url'] = callback_url

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException as e:
            return {'status': False, 'message': f'Connection error: {str(e)}'}

    def verify_transaction(self, reference: str):
        """Verifies the status of a transaction using its reference."""
        url = f'{self.base_url}/transaction/verify/{reference}'

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException as e:
            return {'status': False, 'message': f'Connection error: {str(e)}'}

    def create_subaccount(self, business_name: str, settlement_bank: str, account_number: str, percentage_charge: float = 20.0, description: str = None):
        """
        Creates a Paystack subaccount for split payments.
        settlement_bank: bank code (e.g. '058' for GTBank, '057' for Zenith)
        account_number: 10-digit NUBAN
        percentage_charge: platform commission percentage (e.g. 20.0% platform commission, 80% to collector)
        """
        url = f'{self.base_url}/subaccount'
        payload = {
            'business_name': business_name,
            'settlement_bank': settlement_bank,
            'account_number': str(account_number),
            'percentage_charge': percentage_charge,
        }
        if description:
            payload['description'] = description

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException as e:
            return {'status': False, 'message': f'Connection error: {str(e)}'}

    def list_banks(self, country: str = 'nigeria'):
        """Fetches list of banks supported by Paystack."""
        url = f'{self.base_url}/bank?country={country}'
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException as e:
            return {'status': False, 'message': f'Connection error: {str(e)}'}

    def resolve_account_number(self, account_number: str, bank_code: str):
        """Verifies account number against bank code to get account name."""
        url = f'{self.base_url}/bank/resolve?account_number={account_number}&bank_code={bank_code}'
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException as e:
            return {'status': False, 'message': f'Connection error: {str(e)}'}