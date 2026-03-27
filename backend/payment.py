import hashlib
import hmac
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class PaymentGateway:
    def __init__(self, provider: str):
        self.provider = provider
        if provider == "jazzcash":
            self.merchant_id = os.getenv("JAZZCASH_MERCHANT_ID", "")
            self.password = os.getenv("JAZZCASH_PASSWORD", "")
            self.integrity_salt = os.getenv("JAZZCASH_INTEGRITY_SALT", "")
            self.base_url = os.getenv("JAZZCASH_API_URL", "https://sandbox.jazzcash.com.pk")
        elif provider == "easypaisa":
            self.store_id = os.getenv("EASYPAISA_STORE_ID", "")
            self.hash_key = os.getenv("EASYPAISA_HASH_KEY", "")
            self.base_url = os.getenv("EASYPAISA_API_URL", "https://sandbox-developer.easypaisa.com.pk")

    def generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        suffix = self.merchant_id[-4:] if self.provider == "jazzcash" else self.store_id[-4:]
        return f"T{timestamp}{suffix}"

    def calculate_hash_jazzcash(self, data: Dict) -> str:
        """Calculate HMAC-SHA256 hash for JazzCash"""
        # Order matters for hash calculation
        sorted_string = "&".join([
            str(data.get(key, ""))
            for key in sorted(data.keys())
            if key != "pp_SecureHash"
        ])
        sorted_string = self.integrity_salt + "&" + sorted_string
        
        return hmac.new(
            self.integrity_salt.encode(),
            sorted_string.encode(),
            hashlib.sha256
        ).hexdigest().upper()

    def initiate_payment_jazzcash(self, amount: float, customer_email: str, 
                                  customer_mobile: str, description: str) -> Dict:
        """Initiate JazzCash payment transaction"""
        transaction_id = self.generate_transaction_id()
        current_time = datetime.now()
        
        data = {
            "pp_Version": "1.1",
            "pp_TxnType": "MWALLET",
            "pp_Language": "EN",
            "pp_MerchantID": self.merchant_id,
            "pp_SubMerchantID": "",
            "pp_Password": self.password,
            "pp_TxnRefNo": transaction_id,
            "pp_Amount": str(int(amount * 100)),  # Convert to paisa
            "pp_TxnCurrency": "PKR",
            "pp_TxnDateTime": current_time.strftime("%Y%m%d%H%M%S"),
            "pp_BillReference": transaction_id,
            "pp_Description": description,
            "pp_TxnExpiryDateTime": (current_time + timedelta(hours=1)).strftime("%Y%m%d%H%M%S"),
            "pp_ReturnURL": f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/payment/callback",
            "ppmpf_1": customer_email,
            "ppmpf_2": customer_mobile,
        }
        
        # Calculate and add secure hash
        data["pp_SecureHash"] = self.calculate_hash_jazzcash(data)
        
        try:
            # Make API request
            response = requests.post(
                f"{self.base_url}/CustomerPortal/transactionmanagement/merchantForm",
                data=data,
                timeout=30
            )
            
            return {
                "transaction_id": transaction_id,
                "payment_url": f"{self.base_url}/CustomerPortal/transactionmanagement/merchantForm",
                "form_data": data,
                "status": "initiated" if response.status_code == 200 else "failed"
            }
        except requests.RequestException as e:
            return {
                "transaction_id": transaction_id,
                "payment_url": None,
                "error": str(e),
                "status": "failed"
            }

    def calculate_hash_easypaisa(self, data: Dict) -> str:
        """Calculate hash for Easypaisa"""
        hash_string = f"{data['amount']}{data['orderRefNum']}{self.store_id}{data['postBackURL']}{self.hash_key}"
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def initiate_payment_easypaisa(self, amount: float, customer_email: str,
                                   customer_mobile: str, description: str) -> Dict:
        """Initiate Easypaisa payment transaction"""
        transaction_id = self.generate_transaction_id()
        
        data = {
            "storeId": self.store_id,
            "amount": str(amount),
            "postBackURL": f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/api/payment/easypaisa/callback",
            "orderRefNum": transaction_id,
            "expiryDate": (datetime.now() + timedelta(hours=1)).strftime("%Y%m%d %H%M%S"),
            "autoRedirect": "1",
            "paymentMethod": "MA_PAYMENT_METHOD",
            "emailAddress": customer_email,
            "mobileNumber": customer_mobile,
        }
        
        # Calculate hash
        data["merchantHashedReq"] = self.calculate_hash_easypaisa(data)
        
        try:
            # Create payment request
            response = requests.post(
                f"{self.base_url}/api/v1/checkout",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            result = response.json() if response.status_code == 200 else {}
            
            return {
                "transaction_id": transaction_id,
                "payment_url": result.get("checkoutUrl"),
                "token": result.get("token"),
                "status": "initiated" if response.status_code == 200 else "failed"
            }
        except requests.RequestException as e:
            return {
                "transaction_id": transaction_id,
                "payment_url": None,
                "error": str(e),
                "status": "failed"
            }

    def verify_payment_jazzcash(self, transaction_data: Dict) -> bool:
        """Verify JazzCash payment callback"""
        received_hash = transaction_data.get("pp_SecureHash", "")
        calculated_hash = self.calculate_hash_jazzcash(transaction_data)
        return received_hash.upper() == calculated_hash.upper()

    def verify_payment_easypaisa(self, transaction_data: Dict) -> bool:
        """Verify Easypaisa payment callback"""
        received_hash = transaction_data.get("merchantHashedReq", "")
        calculated_hash = self.calculate_hash_easypaisa(transaction_data)
        return received_hash == calculated_hash

    def verify_payment(self, transaction_data: Dict) -> bool:
        """Verify payment callback"""
        if self.provider == "jazzcash":
            return self.verify_payment_jazzcash(transaction_data)
        elif self.provider == "easypaisa":
            return self.verify_payment_easypaisa(transaction_data)
        return False

    def get_payment_status(self, response_code: str) -> str:
        """Get standardized payment status from provider response code"""
        success_codes = ["000", "00", "0"]
        if response_code in success_codes:
            return "completed"
        return "failed"

