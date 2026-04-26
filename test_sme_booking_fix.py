#!/usr/bin/env python
"""
Comprehensive test script to verify that SME bulk booking and schedule booking work correctly
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loadify_backend.settings')
django.setup()

from decimal import Decimal
from loadify_api.serializers import (
    BulkBookingCreateSerializer,
    ScheduledPickupSerializer
)

def test_sme_bulk_booking():
    """Test SME bulk booking with large decimal values"""
    
    print("Testing SME Bulk Booking with large decimal values...")
    
    # Test data with values that would previously exceed the 10-digit limit
    test_data = {
        'route': 'Long Distance Route - Karachi to Lahore',
        'pickup_location': 'Karachi',
        'drop_location': 'Lahore',
        'pickup_address': 'Industrial Area, Karachi',
        'drop_address': 'Industrial Area, Lahore',
        'weights': [Decimal('123456789.01'), Decimal('987654321.99'), Decimal('555555555.50')],  # These exceed 10 digits
        'calculated_budgets': [Decimal('1234567890.12'), Decimal('9876543210.98'), Decimal('5555555555.75')],
        'final_budgets': [Decimal('1234567890.15'), Decimal('9876543210.99'), Decimal('5555555555.80')]
    }
    
    serializer = BulkBookingCreateSerializer(data=test_data)
    
    if serializer.is_valid():
        print("✅ SUCCESS: SME Bulk Booking accepts large decimal values!")
        return True
    else:
        print("❌ FAILED: SME Bulk Booking validation errors:")
        print(f"Errors: {serializer.errors}")
        return False

def test_sme_schedule_booking():
    """Test SME schedule booking with large decimal values"""
    
    print("\nTesting SME Schedule Booking with large decimal values...")
    
    test_data = {
        'pickup_date': '2026-12-31',
        'pickup_time': '14:30:00',
        'route': 'Scheduled Route - Islamabad to Peshawar',
        'pickup_location': 'Islamabad',
        'drop_location': 'Peshawar',
        'pickup_address': 'Business Center, Islamabad',
        'drop_address': 'Market Area, Peshawar',
        'weight': Decimal('999999999.99'),  # 12 digits total
        'load_type': 'Normal',
        'load_mode': 'Full',
        'calculated_budget': Decimal('9999999999.99'),  # 13 digits total
        'final_budget': Decimal('9999999999.99')
    }
    
    serializer = ScheduledPickupSerializer(data=test_data)
    
    if serializer.is_valid():
        print("✅ SUCCESS: SME Schedule Booking accepts large decimal values!")
        return True
    else:
        print("❌ FAILED: SME Schedule Booking validation errors:")
        print(f"Errors: {serializer.errors}")
        return False

def test_extreme_values():
    """Test with extremely large values to ensure robustness"""
    
    print("\nTesting with extremely large decimal values...")
    
    # Test bulk booking with extreme values
    bulk_test_data = {
        'route': 'Extreme Value Test Route',
        'pickup_location': 'City A',
        'drop_location': 'City B',
        'weights': [Decimal('999999999999.99')],  # 14 digits total
        'final_budgets': [Decimal('999999999999.99')]
    }
    
    bulk_serializer = BulkBookingCreateSerializer(data=bulk_test_data)
    bulk_success = bulk_serializer.is_valid()
    
    # Test schedule booking with extreme values
    schedule_test_data = {
        'pickup_date': '2026-12-31',
        'pickup_time': '10:00:00',
        'route': 'Extreme Value Schedule Route',
        'pickup_location': 'City X',
        'drop_location': 'City Y',
        'weight': Decimal('999999999999.99'),  # 14 digits total
        'load_type': 'Normal',
        'load_mode': 'Partial',
        'calculated_budget': Decimal('999999999999.99'),
        'final_budget': Decimal('999999999999.99')
    }
    
    schedule_serializer = ScheduledPickupSerializer(data=schedule_test_data)
    schedule_success = schedule_serializer.is_valid()
    
    if bulk_success and schedule_success:
        print("✅ SUCCESS: Extreme values work correctly!")
        return True
    else:
        print("❌ FAILED: Extreme values rejected:")
        if not bulk_success:
            print(f"Bulk Booking Errors: {bulk_serializer.errors}")
        if not schedule_success:
            print(f"Schedule Booking Errors: {schedule_serializer.errors}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("COMPREHENSIVE SME BOOKING TEST")
    print("=" * 70)
    
    success1 = test_sme_bulk_booking()
    success2 = test_sme_schedule_booking()
    success3 = test_extreme_values()
    
    print("\n" + "=" * 70)
    if success1 and success2 and success3:
        print("🎉 ALL TESTS PASSED!")
        print("✅ SME Bulk Booking is working correctly")
        print("✅ SME Schedule Booking is working correctly")
        print("✅ Both can handle large decimal values without '10 digits' errors")
    else:
        print("⚠️  SOME TESTS FAILED!")
        print("The fix may need additional work.")
        if not success1:
            print("❌ SME Bulk Booking still has issues")
        if not success2:
            print("❌ SME Schedule Booking still has issues")
        if not success3:
            print("❌ Extreme value handling needs improvement")
    print("=" * 70)
