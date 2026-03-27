import pytest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment import PaymentGateway


class TestJazzCashPayment:
    """Test cases for JazzCash payment integration"""

    def setup_method(self):
        """Set up test fixtures"""
        # Set mock environment variables for testing
        os.environ['JAZZCASH_MERCHANT_ID'] = 'TEST_MERCHANT'
        os.environ['JAZZCASH_PASSWORD'] = 'TEST_PASSWORD'
        os.environ['JAZZCASH_INTEGRITY_SALT'] = 'TEST_SALT_12345'
        os.environ['JAZZCASH_API_URL'] = 'https://sandbox.jazzcash.com.pk'
        os.environ['FRONTEND_URL'] = 'http://localhost:5173'
        
        self.gateway = PaymentGateway("jazzcash")

    def test_gateway_initialization(self):
        """Test JazzCash gateway initializes correctly"""
        assert self.gateway.provider == "jazzcash"
        assert self.gateway.merchant_id == "TEST_MERCHANT"
        assert self.gateway.password == "TEST_PASSWORD"
        assert self.gateway.integrity_salt == "TEST_SALT_12345"

    def test_transaction_id_generation(self):
        """Test transaction ID is generated correctly"""
        transaction_id = self.gateway.generate_transaction_id()
        
        assert transaction_id is not None
        assert transaction_id.startswith('T')
        assert len(transaction_id) > 10

    def test_hash_calculation(self):
        """Test HMAC-SHA256 hash calculation for JazzCash"""
        data = {
            "pp_Amount": "10000",
            "pp_TxnRefNo": "T20240101120000TEST"
        }
        
        hash_result = self.gateway.calculate_hash_jazzcash(data)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex length
        assert hash_result.isupper()  # Should be uppercase

    def test_hash_consistency(self):
        """Test that same data produces same hash"""
        data = {
            "pp_Amount": "10000",
            "pp_TxnRefNo": "T20240101120000TEST",
            "pp_MerchantID": "TEST_MERCHANT"
        }
        
        hash1 = self.gateway.calculate_hash_jazzcash(data)
        hash2 = self.gateway.calculate_hash_jazzcash(data)
        
        assert hash1 == hash2

    def test_payment_initiation_structure(self):
        """Test payment initiation returns correct structure"""
        result = self.gateway.initiate_payment_jazzcash(
            amount=100.0,
            customer_email="test@example.com",
            customer_mobile="03001234567",
            description="Test payment"
        )
        
        assert "transaction_id" in result
        assert "status" in result
        assert result["status"] in ["initiated", "failed"]
        assert result["transaction_id"].startswith('T')

    def test_payment_verification_invalid_hash(self):
        """Test payment verification fails with invalid hash"""
        transaction_data = {
            "pp_SecureHash": "INVALID_HASH",
            "pp_Amount": "10000",
            "pp_TxnRefNo": "T20240101120000"
        }
        
        is_valid = self.gateway.verify_payment_jazzcash(transaction_data)
        
        assert is_valid == False

    def test_payment_status_mapping(self):
        """Test payment status is correctly mapped from response codes"""
        assert self.gateway.get_payment_status("000") == "completed"
        assert self.gateway.get_payment_status("00") == "completed"
        assert self.gateway.get_payment_status("0") == "completed"
        assert self.gateway.get_payment_status("124") == "failed"
        assert self.gateway.get_payment_status("error") == "failed"


class TestEasypaisaPayment:
    """Test cases for Easypaisa payment integration"""

    def setup_method(self):
        """Set up test fixtures"""
        os.environ['EASYPAISA_STORE_ID'] = 'TEST_STORE'
        os.environ['EASYPAISA_HASH_KEY'] = 'TEST_HASH_KEY'
        os.environ['EASYPAISA_API_URL'] = 'https://sandbox-developer.easypaisa.com.pk'
        os.environ['BACKEND_URL'] = 'http://localhost:8000'
        
        self.gateway = PaymentGateway("easypaisa")

    def test_gateway_initialization(self):
        """Test Easypaisa gateway initializes correctly"""
        assert self.gateway.provider == "easypaisa"
        assert self.gateway.store_id == "TEST_STORE"
        assert self.gateway.hash_key == "TEST_HASH_KEY"

    def test_transaction_id_generation(self):
        """Test transaction ID is generated correctly"""
        transaction_id = self.gateway.generate_transaction_id()
        
        assert transaction_id is not None
        assert transaction_id.startswith('T')

    def test_hash_calculation(self):
        """Test hash calculation for Easypaisa"""
        data = {
            "amount": "100",
            "orderRefNum": "T20240101120000",
            "postBackURL": "http://localhost:8000/api/payment/easypaisa/callback"
        }
        
        hash_result = self.gateway.calculate_hash_easypaisa(data)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex length

    def test_payment_initiation_structure(self):
        """Test payment initiation returns correct structure"""
        result = self.gateway.initiate_payment_easypaisa(
            amount=100.0,
            customer_email="test@example.com",
            customer_mobile="03001234567",
            description="Test payment"
        )
        
        assert "transaction_id" in result
        assert "status" in result
        assert result["transaction_id"].startswith('T')


class TestPaymentGatewayGeneric:
    """Generic tests for payment gateway"""

    def test_verify_payment_with_unknown_provider(self):
        """Test verification with unknown provider returns False"""
        gateway = PaymentGateway("unknown")
        
        result = gateway.verify_payment({"some": "data"})
        
        assert result == False

    def test_amount_conversion(self):
        """Test amount is correctly converted for payment"""
        os.environ['JAZZCASH_MERCHANT_ID'] = 'TEST'
        os.environ['JAZZCASH_PASSWORD'] = 'TEST'
        os.environ['JAZZCASH_INTEGRITY_SALT'] = 'TEST'
        
        gateway = PaymentGateway("jazzcash")
        
        # JazzCash requires amount in paisa (multiply by 100)
        result = gateway.initiate_payment_jazzcash(
            amount=150.50,
            customer_email="test@test.com",
            customer_mobile="03001234567",
            description="Test"
        )
        
        # Check that form_data contains correct amount
        if result.get("form_data"):
            assert result["form_data"]["pp_Amount"] == "15050"


class TestPaymentValidation:
    """Test input validation for payments"""

    def setup_method(self):
        os.environ['JAZZCASH_MERCHANT_ID'] = 'TEST'
        os.environ['JAZZCASH_PASSWORD'] = 'TEST'
        os.environ['JAZZCASH_INTEGRITY_SALT'] = 'TEST'
        self.gateway = PaymentGateway("jazzcash")

    def test_payment_with_zero_amount(self):
        """Test payment initiation with zero amount"""
        result = self.gateway.initiate_payment_jazzcash(
            amount=0,
            customer_email="test@test.com",
            customer_mobile="03001234567",
            description="Test"
        )
        
        # Should still return a result (validation happens at API level)
        assert "transaction_id" in result

    def test_payment_with_special_characters_in_description(self):
        """Test payment with special characters in description"""
        result = self.gateway.initiate_payment_jazzcash(
            amount=100,
            customer_email="test@test.com",
            customer_mobile="03001234567",
            description="Test & Payment <script>alert('xss')</script>"
        )
        
        assert "transaction_id" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

