#!/usr/bin/env python
"""
Test script to verify that the decimal field fix allows larger values
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loadify_backend.settings')
django.setup()

from decimal import Decimal
from loadify_api.serializers import BulkBookingCreateSerializer

def test_large_decimal_values():
    """Test that the serializer now accepts larger decimal values"""
    
    print("Testing bulk booking serializer with large decimal values...")
    
    # Test data with values that would previously exceed the 10-digit limit
    test_data = {
        'route': 'Test Route - Long Distance',
        'pickup_location': 'City A',
        'drop_location': 'City B',
        'weights': [Decimal('123456789.01'), Decimal('987654321.99')],  # These exceed 10 digits
        'calculated_budgets': [Decimal('1234567890.12'), Decimal('9876543210.98')],
        'final_budgets': [Decimal('1234567890.15'), Decimal('9876543210.99')]
    }
    
    serializer = BulkBookingCreateSerializer(data=test_data)
    
    if serializer.is_valid():
        print("✅ SUCCESS: Large decimal values are now accepted!")
        print(f"Validated data: {serializer.validated_data}")
        return True
    else:
        print("❌ FAILED: Validation errors still exist:")
        print(f"Errors: {serializer.errors}")
        return False

def test_very_large_values():
    """Test with even larger values to ensure the fix works properly"""
    
    print("\nTesting with very large decimal values...")
    
    test_data = {
        'route': 'Test Route - Very Large Values',
        'pickup_location': 'City X',
        'drop_location': 'City Y',
        'weights': [Decimal('99999999999.99')],  # 14 digits total
        'final_budgets': [Decimal('99999999999.99')]
    }
    
    serializer = BulkBookingCreateSerializer(data=test_data)
    
    if serializer.is_valid():
        print("✅ SUCCESS: Very large decimal values are accepted!")
        return True
    else:
        print("❌ FAILED: Very large values rejected:")
        print(f"Errors: {serializer.errors}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("TESTING DECIMAL FIELD FIX")
    print("=" * 60)
    
    success1 = test_large_decimal_values()
    success2 = test_very_large_values()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED! The fix is working correctly.")
        print("SME bulk booking should now work with larger values.")
    else:
        print("⚠️  SOME TESTS FAILED. The fix may need additional work.")
    print("=" * 60)
