# Import Decimal and ROUND_HALF_UP from the decimal module for precise decimal arithmetic and rounding
from decimal import Decimal, ROUND_HALF_UP
# Import datetime class from the datetime module to handle date and time operations
from datetime import datetime
# Import BytesIO from the io module to handle in-memory binary streams (e.g., for PDF generation)
from io import BytesIO
# Import the logging module to enable logging of errors and information
import logging
# Import the random module to generate random numbers (used for OTP generation)
import random
# Import lru_cache from functools to cache the results of the get_truck_db_columns function
from functools import lru_cache

# Import the get_user_model function to retrieve the currently active User model
from django.contrib.auth import get_user_model
# Import the cache framework from Django's core cache to store temporary data (e.g., OTPs)
from django.core.cache import cache
# Import send_mail from Django's core mail to send emails (e.g., password reset OTP)
from django.core.mail import send_mail
# Import connection and transaction from Django's db module to execute raw SQL and manage database transactions
from django.db import connection, transaction
# Import Q for complex queries and Sum for aggregation from Django's ORM
from django.db.models import Q, Sum
# Import HttpResponse and JsonResponse from Django's http module to return HTTP responses
from django.http import HttpResponse, JsonResponse
# Import timezone from Django's utils to handle timezone-aware datetime operations
from django.utils import timezone
# Import status from Django REST framework to use standard HTTP status codes
from rest_framework import status
# Import Response from DRF to return API responses
from rest_framework.response import Response
# Import APIView from DRF to create class-based views
from rest_framework.views import APIView

# Import all necessary models from the current app's models module
from .models import (
    Booking,
    BulkBooking,
    BulkBookingItem,
    Invoice,
    Load,
    LoadStatusHistory,
    RepeatOrder,
    ScheduledPickup,
    Truck,
)
# Import all necessary serializers from the current app's serializers module
from .serializers import (
    BulkBookingCreateSerializer,
    BulkBookingSerializer,
    LoadSerializer,
    LoadStatusHistorySerializer,
    LoginSerializer,
    RegisterSerializer,
    SMEDashboardSummarySerializer,
    SMEInvoiceSerializer,
    SMERepeatOrderSourceSerializer,
    SMEShipmentSerializer,
    ScheduledPickupSerializer,
)

# Retrieve the currently active User model (typically the custom User model)
User = get_user_model()
# Define allowed status transitions for loads
ALLOWED_STATUS_FLOW = {
    "Pending": {"Accepted"},
    "Accepted": {"Picked"},
    "Picked": {"Completed"},
}

# Create a logger for this module to log errors with a specific logger name
logger = logging.getLogger(__name__)
# Prefix for cache keys used for password reset OTP
PASSWORD_RESET_OTP_PREFIX = "password_reset_otp"
# Expiry time for password reset OTP in seconds (10 minutes)
PASSWORD_RESET_OTP_EXPIRY_SECONDS = 10 * 60
# Constant budget rate per kilometer (PKR 70)
BUDGET_RATE_PER_KM = Decimal("70")
# Constant budget rate per ton (PKR 500)
BUDGET_RATE_PER_TON = Decimal("500")


# Define a custom APIView subclass that catches all unhandled exceptions and returns a safe error response
class SafeAPIView(APIView):
    # Override the dispatch method to wrap super().dispatch() in a try-except
    def dispatch(self, request, *args, **kwargs):
        try:
            # Call the parent dispatch method and return its result
            return super().dispatch(request, *args, **kwargs)
        except Exception as exc:
            # Log the full exception traceback with the view class name
            logger.exception("Unhandled error in %s", self.__class__.__name__)
            # Return a JSON response with error details and a 500 status code
            return JsonResponse(
                {
                    "error": "Internal server error",
                    "details": str(exc),
                    "view": self.__class__.__name__,
                },
                status=500,
            )


# Helper function to convert a value to a Decimal, defaulting to 0 if None or empty string
def normalize_decimal(value):
    # If value is None or an empty string, return Decimal("0")
    if value in (None, ""):
        return Decimal("0")
    # Otherwise, convert the value to a string and then to a Decimal
    return Decimal(str(value))


# Helper function to safely get a field value from a truck object, with an optional default
def get_truck_field_value(truck, field_name, default=None):
    # If truck is falsy (None), return the default value
    if not truck:
        return default
    # Return the attribute value from the truck's __dict__, using the default if not found
    return truck.__dict__.get(field_name, default)


# Cache the result of fetching all column names for the Truck table to avoid repeated introspection
@lru_cache(maxsize=1)
def get_truck_db_columns():
    try:
        # Use a database cursor to get the table description for the Truck model's table
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, Truck._meta.db_table)
        # Extract column names from the description and return as a set
        return {col.name for col in description}
    except Exception:
        # If introspection fails, fall back to a minimal set of known legacy columns
        return {"id", "driver_id", "truck_type", "registration_no", "total_capacity", "available_capacity", "preferred_routes", "availability_posted"}


# Check if a given column name exists in the Truck table
def truck_column_exists(column_name):
    # Return True if column_name is in the set of known columns
    return column_name in get_truck_db_columns()


# Check if the Truck table has the columns used_capacity and remaining_capacity
def truck_supports_partial_capacity_columns():
    # Return True if both columns exist
    return truck_column_exists("used_capacity") and truck_column_exists("remaining_capacity")


# Filter a list of field names to include only those that actually exist in the Truck table
def safe_truck_update_fields(update_fields):
    allowed = []
    # Iterate over each field in the update_fields list
    for field in update_fields:
        # Skip fields that are not present in the database
        if field in {"used_capacity", "remaining_capacity", "pickup_city", "drop_city"} and not truck_column_exists(field):
            continue
        # Add allowed fields to the list
        allowed.append(field)
    return allowed


# Save a truck instance only with fields that are safe (present in the database)
def save_truck_fields(truck, update_fields):
    # Filter the update_fields to only those that exist in the database
    filtered = safe_truck_update_fields(update_fields)
    # If there are any fields to save, call save() with update_fields to optimize the query
    if filtered:
        truck.save(update_fields=filtered)


# Return a queryset for trucks that retrieves only the needed fields (optimized)
def get_truck_queryset():
    # List of base fields that are assumed to always exist
    base_fields = [
        "id",
        "driver_id",
        "truck_type",
        "registration_no",
        "total_capacity",
        "available_capacity",
        "preferred_routes",
    ]
    # List of optional fields that may or may not exist in the database
    optional_fields = ["availability_posted", "used_capacity", "remaining_capacity", "pickup_city", "drop_city"]
    # Build the final list of fields to include: base fields plus optional fields that exist
    only_fields = base_fields + [field for field in optional_fields if truck_column_exists(field)]
    # Return a queryset that only selects those fields (using .only())
    return Truck.objects.only(*only_fields)


# Check if a truck has its availability posted (boolean conversion)
def is_truck_availability_posted(truck):
    # Get the value of availability_posted from the truck and convert to boolean
    return bool(get_truck_field_value(truck, "availability_posted", False))


# Convert a value to Decimal, returning None if the input is None or empty
def parse_optional_decimal(value):
    # If value is None or empty string, return None
    if value in (None, ""):
        return None
    # Convert to string and then to Decimal
    return Decimal(str(value))


# Attempt to round a value to a given number of decimal places, returning None if invalid (currently not used correctly)
def rounded_decimal_or_none(value, decimal_places):
    # If value is None or empty, return None (note: this function never uses decimal_places)
    if value in (None, ""):
        return None


# Convert a value to Decimal, returning None if conversion fails
def parse_decimal_or_none(value):
    # If value is None or empty, return None
    if value in (None, ""):
        return None
    try:
        # Try to convert the string representation to Decimal
        return Decimal(str(value))
    except Exception:
        # Return None if any error occurs
        return None


# Calculate the base budget for a load based on distance in km and weight in kg
def calculate_base_budget(distance_km, weight_kg):
    # Normalize the distance to a Decimal, defaulting to 0
    distance = normalize_decimal(distance_km)
    # Normalize the weight to a Decimal, defaulting to 0
    weight = normalize_decimal(weight_kg)
    # If distance is negative, set it to 0
    if distance < 0:
        distance = Decimal("0")
    # If weight is negative, set it to 0
    if weight < 0:
        weight = Decimal("0")
    # Convert weight from kg to tons by dividing by 1000
    weight_tons = weight / Decimal("1000")
    # Calculate total budget: (distance * rate per km) + (weight_tons * rate per ton)
    total = (distance * BUDGET_RATE_PER_KM) + (weight_tons * BUDGET_RATE_PER_TON)
    # Round the total to 2 decimal places using half-up rounding
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Resolve and validate the calculated_budget and final_budget values
def resolve_and_validate_budget(distance_km, weight_kg, calculated_budget_input, final_budget_input):
    # Compute the base minimum budget
    base_budget = calculate_base_budget(distance_km, weight_kg)
    # Parse the input values to Decimal or None
    calculated_budget = parse_decimal_or_none(calculated_budget_input)
    final_budget = parse_decimal_or_none(final_budget_input)

    # If calculated_budget is not provided, default to the base budget
    if calculated_budget is None:
        calculated_budget = base_budget
    # If final_budget is not provided, default to the calculated budget
    if final_budget is None:
        final_budget = calculated_budget

    # Enforce that calculated_budget is at least the base budget
    if calculated_budget < base_budget:
        calculated_budget = base_budget
    # Final budget cannot be negative
    if final_budget < 0:
        return None, None, "Budget cannot be negative"
    # Final budget must not be lower than the calculated minimum
    if final_budget < calculated_budget:
        return None, None, "Budget cannot be lower than minimum calculated amount"

    # Return the resolved budgets rounded to two decimals, and no error
    return calculated_budget.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), final_budget.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), None
    # Dead code: this try block was left over and will never execute (indentation error in original)
    try:
        quantizer = Decimal("1").scaleb(-decimal_places)
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
    except Exception:
        return None


# Normalize route-related numeric fields in a payload to prevent database max_digits validation errors
def normalize_route_payload(payload):
    # If payload is not a dictionary, return it unchanged
    if not isinstance(payload, dict):
        return payload

    # Helper to convert any value to Decimal safely, returning None on failure
    def to_decimal(value):
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    # Helper to clamp and round a Decimal value to specified bounds and decimal places
    def clamp_decimal(value, max_abs=None, max_total=None, decimal_places=2):
        d = to_decimal(value)
        if d is None:
            return None
        # Clamp to max_abs (both positive and negative)
        if max_abs is not None:
            if d > max_abs:
                d = max_abs
            elif d < -max_abs:
                d = -max_abs
        # Clamp to max_total (absolute value, but in code it acts on d directly)
        if max_total is not None:
            if d > max_total:
                d = max_total
            elif d < -max_total:
                d = -max_total
        # Create a quantizer for the given number of decimal places
        quantizer = Decimal('1') / Decimal(10 ** decimal_places)
        # Return the clamped and rounded value
        return d.quantize(quantizer, rounding=ROUND_HALF_UP)

    # List of latitude fields
    lat_fields = ['pickup_lat', 'drop_lat']
    # List of longitude fields
    lng_fields = ['pickup_lng', 'drop_lng']

    # Clamp latitude fields to ±90 degrees with 7 decimal places
    for field in lat_fields:
        if field in payload and payload[field] is not None:
            clamped = clamp_decimal(payload[field], max_abs=Decimal('90'), decimal_places=7)
            payload[field] = str(clamped) if clamped is not None else payload[field]

    # Clamp longitude fields to ±180 degrees with 7 decimal places
    for field in lng_fields:
        if field in payload and payload[field] is not None:
            clamped = clamp_decimal(payload[field], max_abs=Decimal('180'), decimal_places=7)
            payload[field] = str(clamped) if clamped is not None else payload[field]

    # Clamp distance fields to a maximum of 9,999,999.99 and 2 decimal places
    for key in ['route_distance_km', 'route_distance']:
        if key in payload and payload[key] is not None:
            clamped = clamp_decimal(payload[key], max_total=Decimal('9999999.99'), decimal_places=2)
            if clamped is not None:
                payload[key] = str(clamped)

    # Clamp duration fields: ensure they are integers within 0 and 10,000,000 minutes
    for key in ['route_duration_minutes', 'route_duration']:
        if key in payload and payload[key] not in (None, ''):
            try:
                val = int(float(payload[key]))
                if val < 0:
                    val = 0
                if val > 10_000_000:
                    val = 10_000_000
                payload[key] = val
            except Exception:
                # If conversion fails, keep the original value
                pass

    # If old field name 'route_distance' exists but not 'route_distance_km', copy it over
    if 'route_distance' in payload and 'route_distance_km' not in payload:
        payload['route_distance_km'] = payload['route_distance']
    # Similarly for duration
    if 'route_duration' in payload and 'route_duration_minutes' not in payload:
        payload['route_duration_minutes'] = payload['route_duration']

    # Sanitize weight and budget fields if they are present at the top level
    for field in ['weight', 'calculated_budget', 'final_budget']:
        if field in payload and payload[field] is not None:
            clamped = clamp_decimal(payload[field], max_total=Decimal('9999999.99'), decimal_places=2)
            if clamped is not None:
                payload[field] = str(clamped)

    # Return the normalized payload dictionary
    return payload


# Retrieve the set of active loads for a truck that are accepted or picked
def get_active_truck_loads(truck):
    return Load.objects.filter(truck=truck, status__in=["Accepted", "Picked"])


# Get the remaining capacity of a truck based on database columns
def get_remaining_capacity(truck):
    # If no truck, return 0
    if not truck:
        return Decimal("0")
    # Get total capacity as Decimal
    total_capacity = normalize_decimal(get_truck_field_value(truck, "total_capacity"))
    raw_remaining = None
    # If partial capacity columns exist, try to read remaining_capacity
    if truck_supports_partial_capacity_columns():
        raw_remaining = get_truck_field_value(truck, "remaining_capacity")
    # Otherwise fall back to available_capacity
    if raw_remaining in (None, ""):
        raw_remaining = get_truck_field_value(truck, "available_capacity")
    # Normalize the raw remaining value
    current_remaining = normalize_decimal(raw_remaining if raw_remaining not in (None, "") else total_capacity)
    # Ensure remaining is not negative and not greater than total capacity
    if current_remaining < 0:
        current_remaining = Decimal("0")
    if total_capacity > 0:
        current_remaining = min(current_remaining, total_capacity)
    return current_remaining


# Get the used capacity of a truck
def get_used_capacity(truck):
    # If no truck, return 0
    if not truck:
        return Decimal("0")
    # Get total capacity
    total_capacity = normalize_decimal(get_truck_field_value(truck, "total_capacity"))
    # If partial capacity columns exist, use used_capacity field
    if truck_supports_partial_capacity_columns():
        current_used = normalize_decimal(get_truck_field_value(truck, "used_capacity"))
    else:
        # Otherwise compute used = total - remaining
        current_used = total_capacity - get_remaining_capacity(truck)
    # Ensure used is not negative and not greater than total capacity
    if current_used < 0:
        current_used = Decimal("0")
    if total_capacity > 0:
        current_used = min(current_used, total_capacity)
    return current_used


# Check if a truck has any active full load (load_mode="Full")
def has_active_full_load(truck):
    return get_active_truck_loads(truck).filter(load_mode="Full").exists()


# Synchronize the truck's used_capacity, remaining_capacity, and available_capacity fields
def sync_truck_available_capacity(truck):
    # Get total capacity
    total_capacity = normalize_decimal(get_truck_field_value(truck, "total_capacity"))
    # Get current remaining and used capacities
    normalized_remaining = get_remaining_capacity(truck)
    normalized_used = get_used_capacity(truck)
    # Recompute used from total and remaining if total > 0
    if total_capacity > 0:
        normalized_used = total_capacity - normalized_remaining
        if normalized_used < 0:
            normalized_used = Decimal("0")
    # Prepare list of fields to update
    update_fields = []
    # Update remaining_capacity if the column exists and value differs
    if truck_supports_partial_capacity_columns() and get_truck_field_value(truck, "remaining_capacity") != normalized_remaining:
        truck.remaining_capacity = normalized_remaining
        update_fields.append("remaining_capacity")
    # Update available_capacity if value differs
    if get_truck_field_value(truck, "available_capacity") != normalized_remaining:
        truck.available_capacity = normalized_remaining
        update_fields.append("available_capacity")
    # Update used_capacity if column exists and value differs
    if truck_supports_partial_capacity_columns() and get_truck_field_value(truck, "used_capacity") != normalized_used:
        truck.used_capacity = normalized_used
        update_fields.append("used_capacity")
    # If any fields changed, save the truck with only those fields
    if update_fields:
        save_truck_fields(truck, update_fields)
    # Return the new remaining capacity
    return normalized_remaining


# Get the total capacity of a truck as Decimal
def get_truck_total_capacity(truck):
    # If no truck, return 0
    if not truck:
        return Decimal("0")
    return normalize_decimal(get_truck_field_value(truck, "total_capacity"))


# Validate that a load's weight does not exceed the truck's total capacity for a full load
def validate_single_load_capacity(load_weight, truck):
    # Weight must be positive
    if load_weight <= 0:
        return "Load weight must be greater than zero"

    # Truck capacity must be configured (greater than 0)
    truck_capacity = get_truck_total_capacity(truck)
    if truck_capacity <= 0:
        return "Truck capacity is not configured"

    # Load weight must not exceed truck capacity
    if load_weight > truck_capacity:
        return "Load exceeds your truck capacity"

    # No error
    return None


# Validate that a load's weight fits within the truck's remaining capacity for a partial load
def validate_partial_load_capacity(load_weight, truck):
    # Weight must be positive
    if load_weight <= 0:
        return "Load weight must be greater than zero"

    # Get remaining capacity
    remaining_capacity = get_remaining_capacity(truck)
    # If remaining capacity is 0 or less, truck is full
    if remaining_capacity <= 0:
        return "Truck is full"
    # Load weight must not exceed remaining capacity
    if load_weight > remaining_capacity:
        return "Entered load exceeds available truck capacity"
    # No error
    return None


# Normalize a city name to lowercase stripped string for comparison
def normalize_city(value):
    return str(value or "").strip().lower()


# Check if a truck matches the desired pickup and drop cities (if both specified)
def truck_matches_route(truck, pickup_city, drop_city):
    # Normalize target pickup and drop cities
    target_pickup = normalize_city(pickup_city)
    target_drop = normalize_city(drop_city)
    # If either target is empty, consider a match (no filter)
    if not target_pickup or not target_drop:
        return True
    # Return True if truck's cities match exactly (case-insensitive)
    return (
        normalize_city(get_truck_field_value(truck, "pickup_city")) == target_pickup
        and normalize_city(get_truck_field_value(truck, "drop_city")) == target_drop
    )


# Validate a status transition against allowed flow
def is_valid_status_transition(current_status, next_status):
    # Allow same-status transitions (no change)
    if current_status == next_status:
        return True
    # Check if next_status is in the allowed set for the current status
    return next_status in ALLOWED_STATUS_FLOW.get(current_status, set())


# Serialize a Load instance into a dictionary for API responses
def serialize_load_item(load):
    return {
        "id": load.id,
        "is_scheduled": bool(load.is_scheduled),
        "bulk_booking_id": load.bulk_booking_id,
        "pickup_location": load.pickup_location,
        "drop_location": load.drop_location,
        "pickup_address": load.pickup_address,
        "drop_address": load.drop_address,
        "pickup_lat": load.pickup_lat,
        "pickup_lng": load.pickup_lng,
        "drop_lat": load.drop_lat,
        "drop_lng": load.drop_lng,
        "route_distance_km": load.route_distance_km,
        "route_duration_minutes": load.route_duration_minutes,
        "weight": load.weight,
        "load_type": load.load_type,
        "load_mode": load.load_mode,
        "budget_rate": load.budget_rate,
        "calculated_budget": load.calculated_budget,
        "final_budget": load.final_budget,
        "pickup_time": load.pickup_time,
        "status": load.status,
        "user_id": load.user_id,
        "trader_name": load.user.first_name if load.user else None,
        "trader_phone": load.user.phone_number if load.user else None,
        "trader_email": load.user.email if load.user else None,
        "driver_current_latitude": load.driver_current_latitude,
        "driver_current_longitude": load.driver_current_longitude,
        "driver_location_updated_at": load.driver_location_updated_at,
    }


# Check if a load was created by a user with a specific role (trader or sme)
def load_matches_creator_role(load, target_role):
    normalized_target = str(target_role or "").strip().lower()
    created_role = str(load.created_by_role or "").strip().lower()
    user_role = str(load.user.role if load.user else "").strip().lower()

    # Alias map for inconsistent role strings
    alias_map = {
        "sme": "sme",
        "small and medium enterprise": "sme",
        "trader": "trader",
    }

    # Normalize created role string using alias map
    normalized_created = alias_map.get(created_role, created_role)
    # Normalize user role string using alias map
    normalized_user = alias_map.get(user_role, user_role)

    # If created_by_role is set, compare it to target; otherwise compare user role
    if normalized_created:
        return normalized_created == normalized_target
    return normalized_user == normalized_target


# Serialize a Truck instance into a dictionary for API responses
def serialize_truck_item(truck):
    # Ensure capacity fields are synced and get remaining/used
    remaining_capacity = sync_truck_available_capacity(truck)
    used_capacity = get_used_capacity(truck)
    # Get the associated driver
    driver = truck.driver
    return {
        "id": truck.id,
        "truck_type": truck.truck_type,
        "registration_no": truck.registration_no,
        "total_capacity": get_truck_field_value(truck, "total_capacity"),
        "available_capacity": remaining_capacity,
        "remaining_capacity": remaining_capacity,
        "used_capacity": used_capacity,
        "preferred_routes": get_truck_field_value(truck, "preferred_routes"),
        "pickup_city": get_truck_field_value(truck, "pickup_city"),
        "drop_city": get_truck_field_value(truck, "drop_city"),
        "availability_status": "Full" if remaining_capacity <= 0 else "Available",
        "driver_id": driver.id if driver else None,
        "driver_name": driver.first_name if driver else None,
        "driver_phone": driver.phone_number if driver else None,
        "driver_email": driver.email if driver else None,
        "driver_city": driver.city if driver else None,
        "availability_posted": get_truck_field_value(truck, "availability_posted"),
    }


# Get the truck associated with a driver user (if the user is a driver)
def get_driver_truck(user):
    # If user is not set or not a driver, return None
    if not user or user.role != "driver":
        return None
    # Return the first truck linked to this driver (ordered by id)
    return get_truck_queryset().filter(driver=user).order_by("id").first()


# Serialize a User instance into a dictionary for API responses, including truck details if driver
def serialize_user(user):
    # Get the user's truck if they are a driver
    truck = get_driver_truck(user)
    return {
        "id": user.id,
        "name": user.first_name,
        "fullName": user.first_name,
        "username": user.username,
        "email": user.email,
        "phone": user.phone_number,
        "phone_number": user.phone_number,
        "role": user.role,
        "city": user.city,
        "goods_type": user.goods_type,
        "cnic": user.cnic,
        "business_name": user.business_name,
        "business_type": user.business_type,
        "ntn": user.ntn,
        "owner_name": user.owner_name,
        "business_email": user.business_email,
        "business_address": user.business_address,
        "truckType": truck.truck_type if truck else None,
        "truck_type": truck.truck_type if truck else None,
        "truckReg": truck.registration_no if truck else None,
        "truck_registration_no": truck.registration_no if truck else None,
        "capacity": str(get_truck_field_value(truck, "total_capacity")) if truck and get_truck_field_value(truck, "total_capacity") is not None else None,
        "available_capacity": str(get_remaining_capacity(truck)) if truck else None,
        "remaining_capacity": str(get_remaining_capacity(truck)) if truck else None,
        "used_capacity": str(get_used_capacity(truck)) if truck else None,
        "pickup_city": get_truck_field_value(truck, "pickup_city") if truck else None,
        "drop_city": get_truck_field_value(truck, "drop_city") if truck else None,
    }


# View for user login
class LoginAPI(SafeAPIView):
    def post(self, request):
        # Create a login serializer with request data
        serializer = LoginSerializer(data=request.data)

        # If serializer is valid, login is successful
        if serializer.is_valid():
            # Get the authenticated user from validated data
            user = serializer.validated_data["user"]
            # Return the success message and serialized user
            return Response(
                {
                    "message": "Login successful",
                    "user": serialize_user(user),
                },
                status=status.HTTP_200_OK,
            )

        # If invalid, return error details
        return Response(
            {
                "message": "Login failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# View for user registration
class RegisterAPI(SafeAPIView):
    def post(self, request):
        # Create a register serializer with request data
        serializer = RegisterSerializer(data=request.data)

        # If serializer is valid, save the new user
        if serializer.is_valid():
            user = serializer.save()
            # Return success response with user data
            return Response(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "user": serialize_user(user),
                },
                status=status.HTTP_201_CREATED,
            )

        # If invalid, return error details
        return Response(
            {
                "success": False,
                "message": "Please fix the errors below.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# View for initiating password reset (sends OTP)
class ForgotPasswordAPIView(SafeAPIView):
    def post(self, request):
        # Extract and clean email from request
        email = (request.data.get("email") or "").strip().lower()
        # If email not provided, return error
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Look up the user by email (case-insensitive)
        user = User.objects.filter(email__iexact=email).first()
        # If no user found, return error
        if not user:
            return Response({"error": "No account found with this email"}, status=status.HTTP_404_NOT_FOUND)

        # Generate a 6-digit OTP
        otp_code = f"{random.randint(0, 999999):06d}"
        # Build cache key for this email
        cache_key = f"{PASSWORD_RESET_OTP_PREFIX}:{email}"
        # Store OTP in cache with expiry time
        cache.set(cache_key, otp_code, timeout=PASSWORD_RESET_OTP_EXPIRY_SECONDS)

        try:
            # Send the OTP via email
            send_mail(
                subject="Loadify Password Reset OTP",
                message=(
                    f"Your Loadify password reset OTP is {otp_code}.\n\n"
                    f"This code will expire in {PASSWORD_RESET_OTP_EXPIRY_SECONDS // 60} minutes."
                ),
                from_email=None,  # Use DEFAULT_FROM_EMAIL
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            # If email sending fails, return server error
            return Response(
                {
                    "error": "Unable to send OTP email. Please verify SMTP credentials and Gmail app password.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Return success message
        return Response({"message": "OTP sent to your email"}, status=status.HTTP_200_OK)


# View for resetting password using OTP
class ResetPasswordAPIView(SafeAPIView):
    def post(self, request):
        # Extract email, otp, and new_password from request
        email = (request.data.get("email") or "").strip().lower()
        otp = (request.data.get("otp") or "").strip()
        new_password = request.data.get("new_password") or ""

        # Validate all required fields are present
        if not email or not otp or not new_password:
            return Response(
                {"error": "email, otp and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate password length
        if len(new_password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up user by email
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "No account found with this email"}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve OTP from cache
        cache_key = f"{PASSWORD_RESET_OTP_PREFIX}:{email}"
        expected_otp = cache.get(cache_key)
        # If OTP not found or doesn't match, return error
        if not expected_otp or str(expected_otp) != otp:
            return Response({"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST)

        # Set the new password and save
        user.set_password(new_password)
        user.save(update_fields=["password"])
        # Remove the OTP from cache
        cache.delete(cache_key)

        # Return success
        return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)


# View for creating a new load
class CreateLoadAPIView(SafeAPIView):
    def post(self, request):
        # Deserialize and validate the request data
        serializer = LoadSerializer(data=request.data)

        # If invalid, return validation errors
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract user_id from request data
        user_id = request.data.get("user_id")

        # user_id is mandatory
        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid user_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize driver and truck variables
        assigned_driver = None
        assigned_truck = None
        # Get optional driver_id from request
        driver_id = request.data.get("driver_id")
        # Default load status to "Pending"
        load_status = request.data.get("status") or "Pending"
        # Normalize load weight
        load_weight = normalize_decimal(serializer.validated_data.get("weight"))
        # Get load mode
        load_mode = str(serializer.validated_data.get("load_mode") or "").strip()
        # Get route distance from various possible keys
        route_distance_km = serializer.validated_data.get("route_distance_km") or request.data.get("route_distance_km") or request.data.get("distance_km")
        # Get budget inputs
        calculated_budget_input = request.data.get("calculated_budget")
        final_budget_input = request.data.get("final_budget")
        # If final_budget_input is empty, try budget_rate as fallback
        if final_budget_input in (None, ""):
            final_budget_input = request.data.get("budget_rate")
        # Get requested pickup and drop cities for route matching
        requested_pickup_city = request.data.get("pickup_city")
        requested_drop_city = request.data.get("drop_city")

        # Resolve and validate budgets
        calculated_budget, final_budget, budget_error = resolve_and_validate_budget(
            route_distance_km,
            load_weight,
            calculated_budget_input,
            final_budget_input,
        )
        # If budget validation fails, return error
        if budget_error:
            return Response({"error": budget_error}, status=status.HTTP_400_BAD_REQUEST)

        # If a driver_id is provided, assign the load to that driver
        if driver_id:
            try:
                # Look up the driver user and fetch their truck
                assigned_driver = User.objects.get(id=driver_id, role="driver")
                assigned_truck = get_truck_queryset().filter(driver=assigned_driver).order_by("id").first()
                # Returns error if no truck found
                if not assigned_truck:
                    return Response({"error": "No truck found for this driver"}, status=status.HTTP_400_BAD_REQUEST)

                # If load mode is Partial, perform additional checks
                if load_mode == "Partial":
                    # Truck must have availability posted
                    if not is_truck_availability_posted(assigned_truck):
                        return Response(
                            {"error": "This truck is not currently available for partial booking"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    # Pickup and drop cities must be provided and match truck's route
                    if not requested_pickup_city or not requested_drop_city:
                        return Response(
                            {"error": "pickup_city and drop_city are required for partial booking"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not truck_matches_route(assigned_truck, requested_pickup_city, requested_drop_city):
                        return Response(
                            {"error": "This truck is not available for the selected pickup/drop cities"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    # Validate that the weight fits within remaining capacity
                    capacity_error = validate_partial_load_capacity(load_weight, assigned_truck)
                else:
                    # For full loads, validate against total capacity
                    capacity_error = validate_single_load_capacity(load_weight, assigned_truck)
                # If capacity error, return it
                if capacity_error:
                    return Response(
                        {"error": capacity_error},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # If all checks pass, set load status to "Pre Pending" (private offer)
                load_status = "Pre Pending"
            except User.DoesNotExist:
                # If the driver_id is invalid, return error
                return Response({"error": "Invalid driver_id"}, status=status.HTTP_400_BAD_REQUEST)

        # Determine the creator role (trader or sme)
        creator_role = user.role if user.role in {"trader", "sme"} else None

        # Save the Load object using the serializer's save method with extra fields
        load = serializer.save(
            user=user,
            created_by_role=creator_role,
            is_scheduled=bool(serializer.validated_data.get("pickup_time")),
            driver=assigned_driver,
            truck=assigned_truck,
            budget_rate=final_budget,
            calculated_budget=calculated_budget,
            final_budget=final_budget,
            status=load_status,
        )

        # Return success response with serialized load data
        return Response(
            {
                "message": "Load created successfully",
                "data": LoadSerializer(load).data,
            },
            status=status.HTTP_201_CREATED,
        )


# View to get combined statistics for a user (total/active/completed loads and total earnings)
class UserStatsAPIView(SafeAPIView):
    def get(self, request):
        # Get userId from query parameters
        user_id = request.GET.get("userId")
        # If not provided, return error
        if not user_id:
            return Response({"error": "userId is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Try to fetch the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid userId"}, status=status.HTTP_404_NOT_FOUND)

        # Get all loads for this user
        user_loads = Load.objects.filter(user=user)
        # Filter completed loads
        completed_loads = user_loads.filter(status="Completed")

        # Calculate total earnings from completed loads (by summing budget_rate)
        total_earnings = 0
        for load in completed_loads:
            if load.budget_rate:
                total_earnings += float(load.budget_rate)

        # Return the statistics
        return Response(
            {
                "totalLoads": user_loads.count(),
                "activeLoads": user_loads.filter(status__in=["Pre Pending", "Pending", "Accepted", "Picked"]).count(),
                "completedLoads": completed_loads.count(),
                "totalEarnings": total_earnings,
            }
        )


# View to get load-specific statistics for a user (counts only, no earnings)
class UserLoadStatsAPIView(SafeAPIView):
    def get(self, request):
        # Get userId from query parameters
        user_id = request.GET.get("userId")
        # If not provided, return error
        if not user_id:
            return Response({"error": "userId is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Try to fetch the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid userId"}, status=status.HTTP_404_NOT_FOUND)

        # Get all loads for this user
        user_loads = Load.objects.filter(user=user)
        # Return counts
        return Response(
            {
                "totalLoads": user_loads.count(),
                "activeLoads": user_loads.filter(status__in=["Pre Pending", "Pending", "Accepted", "Picked"]).count(),
                "completedLoads": user_loads.filter(status="Completed").count(),
            }
        )


# View to retrieve a user's profile by email
class UserProfileAPIView(SafeAPIView):
    def get(self, request):
        # Get email from query parameters
        email = request.GET.get("email")
        # If not provided, return error
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Look up user by email (case-insensitive)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Return serialized user data
        return Response(serialize_user(user))


# View to retrieve all loads created by a specific user
class UserLoadsAPIView(SafeAPIView):
    def get(self, request):
        # Get userId from query parameters
        user_id = request.GET.get("userId")
        # If not provided, return error
        if not user_id:
            return Response({"error": "userId is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Look up user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid userId"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch loads for that user, including related user and driver, newest first
        loads = Load.objects.filter(user=user).select_related("user", "driver").order_by("-id")
        # Return list of serialized load items
        return Response([serialize_load_item(load) for load in loads])


# View to list trucks, with optional filtering (search, posted only, pickup/drop cities)
class TruckListAPIView(SafeAPIView):
    def get(self, request):
        # Get search query parameter
        search = (request.GET.get("search") or "").strip()
        # Check if posted_only filter is requested
        posted_only = str(request.GET.get("posted_only", "")).lower() in {"1", "true", "yes"}
        # Get pickup and drop city filters
        pickup_city = (request.GET.get("pickup_city") or "").strip()
        drop_city = (request.GET.get("drop_city") or "").strip()
        # Get base queryset of trucks with active drivers, newest first
        trucks = get_truck_queryset().select_related("driver").filter(driver__isnull=False).order_by("-id")
        # If posted_only filter is on, filter by availability_posted if column exists
        if posted_only:
            if truck_column_exists("availability_posted"):
                trucks = trucks.filter(availability_posted=True)
            else:
                # If column doesn't exist, no truck can be considered posted, return empty list
                return Response([])

        # Apply search filter on truck type, registration, driver name, or driver city
        if search:
            trucks = trucks.filter(
                Q(truck_type__icontains=search)
                | Q(registration_no__icontains=search)
                | Q(driver__first_name__icontains=search)
                | Q(driver__city__icontains=search)
            )

        # Build list of serialized trucks that pass route and capacity checks
        visible_trucks = []
        for truck in trucks:
            # If posted_only and route doesn't match, skip
            if posted_only and not truck_matches_route(truck, pickup_city, drop_city):
                continue
            # Serialize the truck
            serialized = serialize_truck_item(truck)
            # If posted_only and remaining capacity is zero or less, skip
            if posted_only and normalize_decimal(serialized.get("remaining_capacity")) <= 0:
                continue
            visible_trucks.append(serialized)

        # Return the final list
        return Response(visible_trucks)


# View to update a user's profile and optionally their truck details
class UserUpdateAPIView(SafeAPIView):
    def put(self, request):
        # Get userId from request data
        user_id = request.data.get("userId")
        # If not provided, return error
        if not user_id:
            return Response({"error": "userId is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Invalid userId"}, status=status.HTTP_404_NOT_FOUND)

        # Get the user's truck if they are a driver
        truck = get_driver_truck(user)

        # Map of possible request field names to user model fields
        field_map = {
            "name": "first_name",
            "fullName": "first_name",
            "email": "email",
            "phone": "phone_number",
            "phone_number": "phone_number",
            "role": "role",
            "city": "city",
            "goodsType": "goods_type",
            "goods_type": "goods_type",
            "cnic": "cnic",
            "businessName": "business_name",
            "business_name": "business_name",
            "businessType": "business_type",
            "business_type": "business_type",
            "ntn": "ntn",
            "ownerName": "owner_name",
            "owner_name": "owner_name",
            "businessEmail": "business_email",
            "business_email": "business_email",
            "address": "business_address",
            "business_address": "business_address",
        }

        # Update user fields if present in request
        for request_key, model_field in field_map.items():
            if request_key in request.data:
                setattr(user, model_field, request.data.get(request_key))

        # Save the user object
        user.save()

        # If the user is a driver, update truck fields as well
        if truck:
            # Map of request fields to truck model fields
            truck_field_map = {
                "truckType": "truck_type",
                "truck_type": "truck_type",
                "truckReg": "registration_no",
                "truck_registration_no": "registration_no",
                "capacity": "total_capacity",
                "available_capacity": "available_capacity",
                "availableCapacity": "available_capacity",
            }
            # Add optional fields if columns exist
            if truck_supports_partial_capacity_columns():
                truck_field_map["remaining_capacity"] = "remaining_capacity"
            if truck_column_exists("pickup_city"):
                truck_field_map["pickup_city"] = "pickup_city"
            if truck_column_exists("drop_city"):
                truck_field_map["drop_city"] = "drop_city"

            capacity_updated = False
            available_capacity_updated = False
            # Iterate over the truck field map and update attributes
            for request_key, model_field in truck_field_map.items():
                if request_key in request.data:
                    # For capacity/decimal fields, parse optionally
                    if model_field in {"total_capacity", "available_capacity", "remaining_capacity"}:
                        setattr(truck, model_field, parse_optional_decimal(request.data.get(request_key)))
                    else:
                        setattr(truck, model_field, request.data.get(request_key))
                    # Track if total_capacity was updated
                    if model_field == "total_capacity":
                        capacity_updated = True
                    # Track if available/remaining capacity was updated
                    if model_field in {"available_capacity", "remaining_capacity"}:
                        available_capacity_updated = True

            # If total capacity changed, adjust remaining and used accordingly
            if capacity_updated:
                current_available = normalize_decimal(
                    get_truck_field_value(truck, "remaining_capacity")
                    if get_truck_field_value(truck, "remaining_capacity") is not None
                    else get_truck_field_value(truck, "available_capacity")
                )
                new_total_capacity = normalize_decimal(truck.total_capacity)
                new_remaining = min(current_available, new_total_capacity)
                if truck_supports_partial_capacity_columns():
                    truck.remaining_capacity = new_remaining
                truck.available_capacity = new_remaining
                if truck_supports_partial_capacity_columns():
                    truck.used_capacity = max(new_total_capacity - normalize_decimal(new_remaining), Decimal("0"))

            # If available capacity directly updated, ensure it's within bounds
            if available_capacity_updated:
                posted_available = normalize_decimal(
                    get_truck_field_value(truck, "remaining_capacity")
                    if get_truck_field_value(truck, "remaining_capacity") is not None
                    else get_truck_field_value(truck, "available_capacity")
                )
                max_allowed = get_truck_total_capacity(truck)
                if posted_available < 0:
                    new_remaining = Decimal("0")
                else:
                    new_remaining = min(posted_available, max_allowed)
                if truck_supports_partial_capacity_columns():
                    truck.remaining_capacity = new_remaining
                    truck.used_capacity = max(max_allowed - normalize_decimal(new_remaining), Decimal("0"))
                truck.available_capacity = new_remaining

            # Save all truck field updates with safe filtering
            save_truck_fields(
                truck,
                [
                    "truck_type",
                    "registration_no",
                    "total_capacity",
                    "available_capacity",
                    "remaining_capacity",
                    "used_capacity",
                    "pickup_city",
                    "drop_city",
                ],
            )

        # Return the updated user serialized
        return Response(serialize_user(user))


# View to get pending loads (unassigned) and optionally filtered for a specific driver (including private offers)
class PendingLoadsAPIView(SafeAPIView):
    def get(self, request):
        # Base queryset: pending loads with no driver assigned
        loads = Load.objects.filter(status="Pending", driver__isnull=True).select_related("user")
        # Check if a driver_id is provided for filtering
        driver_id = request.GET.get("driver_id")

        # If driver_id provided, do capacity-based filtering and include private offers
        if driver_id:
            try:
                driver = User.objects.get(id=driver_id, role="driver")
            except User.DoesNotExist:
                return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

            # Get the truck for this driver
            truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
            if not truck:
                return Response(
                    {"error": "No truck found for this driver"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get truck capacity and remaining capacity
            truck_capacity = get_truck_total_capacity(truck)
            if truck_capacity <= 0:
                return Response(
                    {"error": "Truck capacity is not configured"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get private offer loads (Pre Pending) for this driver
            private_offer_loads = Load.objects.filter(
                status="Pre Pending",
                driver=driver,
            ).select_related("user")
            # Check if the truck can accept partial loads
            allow_partial = bool(is_truck_availability_posted(truck) and get_remaining_capacity(truck) > 0)
            # If truck cannot do partials or capacity is zero, restrict to Full loads only
            if truck_capacity <= 0 or not allow_partial:
                private_offer_loads = private_offer_loads.filter(load_mode="Full")
                loads = loads.filter(load_mode="Full")
            else:
                # Filter private and public loads by weight within remaining capacity
                private_offer_loads = private_offer_loads.filter(
                    Q(load_mode="Full") | (Q(load_mode="Partial") & Q(weight__gt=0) & Q(weight__lte=get_remaining_capacity(truck)))
                )
                loads = loads.filter(
                    Q(load_mode="Full") | (Q(load_mode="Partial") & Q(weight__gt=0) & Q(weight__lte=get_remaining_capacity(truck)))
                )

            # Merge private offers first then public loads, newest first
            merged_loads = list(private_offer_loads.order_by("-id")) + list(loads.order_by("-id"))
            return Response([serialize_load_item(load) for load in merged_loads])

        # If no driver_id, just return all pending loads newest first
        data = [serialize_load_item(load) for load in loads.order_by("-id")]

        return Response(data)


# Helper function to get request loads for a driver filtered by creator role (trader or sme)
def get_driver_request_loads_by_role(driver, role_value):
    # Get truck and its remaining capacity
    truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
    remaining_capacity = sync_truck_available_capacity(truck) if truck else None

    # Fetch private offer loads for this driver that match the role
    private_offer_loads = [
        load for load in Load.objects.filter(
            status="Pre Pending",
            driver=driver,
        ).select_related("user").order_by("-id")
        if load_matches_creator_role(load, role_value)
    ]

    # Fetch public pending loads that match the role
    pending_loads_qs = Load.objects.filter(
        status="Pending",
        driver__isnull=True,
    ).select_related("user").order_by("-id")
    pending_loads = [load for load in pending_loads_qs if load_matches_creator_role(load, role_value)]

    # Merge the two lists
    merged = private_offer_loads + pending_loads
    # If truck exists, filter by capacity and load mode
    if truck:
        allow_partial = bool(is_truck_availability_posted(truck) and normalize_decimal(remaining_capacity) > 0)
        merged = [
            load
            for load in merged
            if (
                str(load.load_mode or "").strip() == "Full"
                or (
                    allow_partial
                    and
                    str(load.load_mode or "").strip() == "Partial"
                    and normalize_decimal(load.weight) > 0
                    and normalize_decimal(load.weight) <= normalize_decimal(remaining_capacity)
                )
            )
        ]
    # Sort merged list by id descending
    merged = sorted(merged, key=lambda x: x.id, reverse=True)
    # Return truck, remaining capacity, and serialized response
    return truck, remaining_capacity, Response([serialize_load_item(load) for load in merged])


# Helper function to get all request loads for a driver without role filtering
def get_driver_all_request_loads(driver):
    # Similar to above but without role filtering
    truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
    remaining_capacity = sync_truck_available_capacity(truck) if truck else None

    private_offer_loads = list(
        Load.objects.filter(
            status="Pre Pending",
            driver=driver,
        ).select_related("user").order_by("-id")
    )
    pending_loads = list(
        Load.objects.filter(
            status="Pending",
            driver__isnull=True,
        ).select_related("user").order_by("-id")
    )

    merged = private_offer_loads + pending_loads
    if truck:
        allow_partial = bool(is_truck_availability_posted(truck) and normalize_decimal(remaining_capacity) > 0)
        merged = [
            load
            for load in merged
            if (
                str(load.load_mode or "").strip() == "Full"
                or (
                    allow_partial
                    and
                    str(load.load_mode or "").strip() == "Partial"
                    and normalize_decimal(load.weight) > 0
                    and normalize_decimal(load.weight) <= normalize_decimal(remaining_capacity)
                )
            )
        ]
    merged = sorted(merged, key=lambda x: x.id, reverse=True)
    return truck, remaining_capacity, Response([serialize_load_item(load) for load in merged])


# View to get request loads for a driver created by traders only
class DriverTraderRequestsAPIView(SafeAPIView):
    def get(self, request):
        # Get driver_id from query parameters
        driver_id = request.GET.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver exists
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get response filtered by trader role
        _, _, response = get_driver_request_loads_by_role(driver, "trader")
        return response


# View to get request loads for a driver created by SMEs, including due scheduled pickups conversions
class DriverSMERequestsAPIView(SafeAPIView):
    def get(self, request):
        # Get driver_id
        driver_id = request.GET.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Convert any scheduled pickups that are due today into loads
        convert_all_due_scheduled_pickups()

        # Get response filtered by SME role
        _, _, response = get_driver_request_loads_by_role(driver, "sme")
        return response


# View to get all request loads for a driver without role filtering
class DriverRequestsAPIView(SafeAPIView):
    def get(self, request):
        # Get driver_id
        driver_id = request.GET.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get response for all loads
        _, _, response = get_driver_all_request_loads(driver)
        return response


# View to get driver dashboard data (today's schedule, remaining capacity)
class DriverDashboardAPIView(SafeAPIView):
    def get(self, request):
        # Get driver_id
        driver_id = request.GET.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get the driver's truck
        truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
        if not truck:
            return Response({"error": "No truck found for this driver"}, status=status.HTTP_400_BAD_REQUEST)

        # Sync and get remaining capacity
        remaining_capacity = sync_truck_available_capacity(truck)
        # Get today's date in local timezone
        today = timezone.localdate()
        # Get loads for today that are accepted or picked, or pre-pending assigned to this driver
        todays_loads = (
            Load.objects.filter(
                driver=driver,
                status__in=["Pre Pending", "Accepted", "Picked"],
                pickup_time__date=today,
            )
            .select_related("user")
            .order_by("pickup_time", "-id")
        )

        # Return dashboard data
        return Response(
            {
                "driver_id": driver.id,
                "today_date": str(today),
                "remaining_capacity": remaining_capacity,
                "today_schedule_count": todays_loads.count(),
                "today_schedule": [serialize_load_item(load) for load in todays_loads],
            },
            status=status.HTTP_200_OK,
        )


# View to accept a pending load by a driver
class AcceptLoadAPIView(SafeAPIView):
    def post(self, request, load_id):
        # Get driver_id from request data
        driver_id = request.data.get("driver_id")

        # driver_id is mandatory
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get the driver's truck
        truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
        if not truck:
            return Response(
                {"error": "No truck found for this driver"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch the load
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure load is available (Pending and unassigned)
        if load.status != "Pending" or load.driver_id is not None:
            return Response(
                {"error": "This load is no longer available"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate status transition
        if not is_valid_status_transition(load.status, "Accepted"):
            return Response(
                {"error": "Invalid status transition. Allowed flow: Pending -> Accepted -> Picked -> Completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get load weight and mode
        load_weight = normalize_decimal(load.weight)
        load_mode = str(load.load_mode or "").strip()
        # Capacity check based on load mode
        if load_mode == "Partial":
            if not is_truck_availability_posted(truck):
                return Response(
                    {"error": "Partial truck availability is not posted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            capacity_error = validate_partial_load_capacity(load_weight, truck)
        else:
            capacity_error = validate_single_load_capacity(load_weight, truck)
        if capacity_error:
            return Response(
                {"error": capacity_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Assign driver and truck, update status to Accepted
        load.driver = driver
        load.truck = truck
        load.status = "Accepted"
        load.save(update_fields=["driver", "truck", "status"])

        # If partial load, deduct weight from remaining capacity
        if load_mode == "Partial":
            remaining_capacity = get_remaining_capacity(truck)
            new_remaining = remaining_capacity - load_weight
            if new_remaining < 0:
                new_remaining = Decimal("0")
            total_capacity = get_truck_total_capacity(truck)
            truck.remaining_capacity = new_remaining
            truck.available_capacity = new_remaining
            truck.used_capacity = max(total_capacity - new_remaining, Decimal("0"))
            # If no remaining capacity, unpost availability
            if new_remaining <= 0:
                truck.availability_posted = False
                save_truck_fields(truck, ["remaining_capacity", "available_capacity", "used_capacity", "availability_posted"])
            else:
                save_truck_fields(truck, ["remaining_capacity", "available_capacity", "used_capacity"])

        # Return success with serialized load
        return Response(
            {
                "message": "Load accepted successfully",
                "data": LoadSerializer(load).data,
            }
        )


# View to get current active loads (Accepted or Picked) for a driver
class CurrentDriverLoadsAPIView(SafeAPIView):
    def get(self, request):
        # Get driver_id
        driver_id = request.GET.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch loads that are Accepted or Picked for this driver
        loads = (
            Load.objects.filter(driver=driver, status__in=["Accepted", "Picked"])
            .select_related("user", "truck")
            .order_by("-id")
        )

        # Return serialized list
        return Response([serialize_load_item(load) for load in loads])


# View to mark an accepted load as Picked
class PickupLoadAPIView(SafeAPIView):
    def post(self, request, load_id):
        # Get driver_id
        driver_id = request.data.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the load
        try:
            load = Load.objects.select_related("driver").get(id=load_id)
        except Load.DoesNotExist:
            return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the load is assigned to this driver
        if load.driver_id != int(driver_id):
            return Response({"error": "This load is not assigned to this driver"}, status=status.HTTP_403_FORBIDDEN)

        # Load must be in Accepted status
        if load.status != "Accepted":
            return Response(
                {"error": "Only accepted loads can be marked as picked"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate status transition
        if not is_valid_status_transition(load.status, "Picked"):
            return Response(
                {"error": "Invalid status transition. Allowed flow: Pending -> Accepted -> Picked -> Completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if pickup time has passed (for trader/sme loads)
        creator_role = str(load.created_by_role or "").strip().lower()
        owner_role = str(load.user.role if load.user else "").strip().lower()
        if (
            (creator_role in {"trader", "sme"} or owner_role in {"trader", "sme"})
            and load.pickup_time
            and timezone.now() < load.pickup_time
        ):
            return Response(
                {"error": "Pickup time not reached yet"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update status to Picked
        load.status = "Picked"
        load.save(update_fields=["status"])

        # Return success
        return Response(
            {
                "message": "Load marked as picked successfully",
                "data": serialize_load_item(load),
            }
        )


# View to respond (accept or reject) a private offer (Pre Pending) load
class RespondPrePendingLoadAPIView(SafeAPIView):
    def post(self, request, load_id):
        # Get driver_id and action from request
        driver_id = request.data.get("driver_id")
        action = request.data.get("action")

        # driver_id required
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Action must be accept or reject
        if action not in {"accept", "reject"}:
            return Response({"error": "action must be accept or reject"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the Pre Pending load
        try:
            load = Load.objects.get(id=load_id, status="Pre Pending")
        except Load.DoesNotExist:
            return Response({"error": "Pre pending load not found"}, status=status.HTTP_404_NOT_FOUND)

        # The load must be assigned to this driver
        if load.driver_id != int(driver_id):
            return Response({"error": "This load is not assigned to this driver"}, status=status.HTTP_403_FORBIDDEN)

        # If accepted, change status to Pending and clear driver/truck
        if action == "accept":
            load.status = "Pending"
        else:
            load.status = "Rejected"

        # Clear the assignment
        load.driver = None
        load.truck = None
        load.save(update_fields=["status", "driver", "truck"])

        # Return success
        return Response(
            {
                "message": f"Load {action}ed successfully",
                "data": serialize_load_item(load),
            }
        )


# View to mark a picked load as Completed
class CompleteLoadAPIView(SafeAPIView):
    def post(self, request, load_id):
        # Get driver_id
        driver_id = request.data.get("driver_id")
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the load with driver and truck
        try:
            load = Load.objects.select_related("driver", "truck").get(id=load_id)
        except Load.DoesNotExist:
            return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

        # Load must be assigned to this driver
        if load.driver_id != int(driver_id):
            return Response({"error": "This load is not assigned to this driver"}, status=status.HTTP_403_FORBIDDEN)

        # Status must be Picked
        if load.status != "Picked":
            return Response(
                {"error": "Only picked loads can be marked as completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate status transition
        if not is_valid_status_transition(load.status, "Completed"):
            return Response(
                {"error": "Invalid status transition. Allowed flow: Pending -> Accepted -> Picked -> Completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update status
        load.status = "Completed"
        load.save(update_fields=["status"])

        # Sync truck capacity after completion (for future loads)
        if load.truck_id:
            sync_truck_available_capacity(load.truck)

        # Return success
        return Response(
            {
                "message": "Load marked as completed successfully",
                "data": serialize_load_item(load),
            }
        )


# View to update the driver's current location for a specific load
class UpdateDriverLocationAPIView(SafeAPIView):
    def post(self, request, load_id):
        # Get driver_id, latitude, longitude
        driver_id = request.data.get("driver_id")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        # driver_id required
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Latitude and longitude required
        if latitude in (None, "") or longitude in (None, ""):
            return Response(
                {"error": "latitude and longitude are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch the load
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

        # Load must be assigned to this driver
        if load.driver_id != int(driver_id):
            return Response({"error": "This load is not assigned to this driver"}, status=status.HTTP_403_FORBIDDEN)

        # Only active loads (Accepted or Picked) can have location updated
        if load.status not in {"Accepted", "Picked"}:
            return Response(
                {"error": "Location can only be updated for active loads"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update location fields
        load.driver_current_latitude = normalize_decimal(latitude)
        load.driver_current_longitude = normalize_decimal(longitude)
        load.driver_location_updated_at = timezone.now()
        load.save(
            update_fields=[
                "driver_current_latitude",
                "driver_current_longitude",
                "driver_location_updated_at",
            ]
        )

        # Return success
        return Response(
            {
                "message": "Driver location updated successfully",
                "data": serialize_load_item(load),
            }
        )


# View to sync driver location across all picked loads for a driver (one location update applies to all)
class SyncDriverPickedLoadsLocationAPIView(SafeAPIView):
    def post(self, request):
        # Get driver_id, latitude, longitude
        driver_id = request.data.get("driver_id")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        # driver_id required
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Latitude and longitude required
        if latitude in (None, "") or longitude in (None, ""):
            return Response(
                {"error": "latitude and longitude are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get all picked loads for this driver
        picked_loads = Load.objects.filter(driver=driver, status="Picked")
        now = timezone.now()
        # Update location on all picked loads
        picked_loads.update(
            driver_current_latitude=normalize_decimal(latitude),
            driver_current_longitude=normalize_decimal(longitude),
            driver_location_updated_at=now,
        )

        # Refresh the loads to get updated values and serialize
        refreshed_loads = Load.objects.filter(driver=driver, status="Picked").select_related("user", "truck")
        return Response(
            {
                "message": "Driver location synced successfully",
                "updatedLoads": [serialize_load_item(load) for load in refreshed_loads],
            }
        )


# View for a driver to post their truck's availability for partial bookings
class DriverPostAvailabilityAPIView(SafeAPIView):
    def post(self, request):
        # Get driver_id, available_capacity, pickup_city, drop_city
        driver_id = request.data.get("driver_id")
        available_capacity = request.data.get("available_capacity")
        pickup_city = (request.data.get("pickup_city") or "").strip()
        drop_city = (request.data.get("drop_city") or "").strip()

        # driver_id required
        if not driver_id:
            return Response({"error": "driver_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # available_capacity required
        if available_capacity in (None, ""):
            return Response({"error": "available_capacity is required"}, status=status.HTTP_400_BAD_REQUEST)
        # pickup_city and drop_city required
        if not pickup_city or not drop_city:
            return Response({"error": "pickup_city and drop_city are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate driver
        try:
            driver = User.objects.get(id=driver_id, role="driver")
        except User.DoesNotExist:
            return Response({"error": "Invalid driver_id"}, status=status.HTTP_404_NOT_FOUND)

        # Get the driver's truck
        truck = get_truck_queryset().filter(driver=driver).order_by("id").first()
        if not truck:
            return Response({"error": "No truck found for this driver"}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize the available_capacity to Decimal
        try:
            requested_available = normalize_decimal(available_capacity)
        except Exception:
            return Response({"error": "available_capacity must be numeric"}, status=status.HTTP_400_BAD_REQUEST)

        # Capacity cannot be negative
        if requested_available < 0:
            return Response({"error": "available_capacity cannot be negative"}, status=status.HTTP_400_BAD_REQUEST)

        # Update truck fields: set total_capacity to this value, reset used, remaining = this value, set route cities, set posted True
        truck.total_capacity = requested_available
        truck.used_capacity = Decimal("0")
        truck.remaining_capacity = requested_available
        truck.available_capacity = requested_available
        truck.pickup_city = pickup_city
        truck.drop_city = drop_city
        truck.availability_posted = True
        save_truck_fields(
            truck,
            [
                "total_capacity",
                "used_capacity",
                "remaining_capacity",
                "available_capacity",
                "pickup_city",
                "drop_city",
                "availability_posted",
            ],
        )

        # Return serialized truck
        return Response(
            {
                "message": "Availability updated successfully",
                "truck": serialize_truck_item(truck),
            }
        )


# Helper to extract the SME user from request (authentication or query param)
def get_sme_user_from_request(request):
    # If request has an authenticated user and that user is an SME, return that user
    if getattr(request, "user", None) and request.user.is_authenticated:
        if request.user.role != "sme":
            return None, Response({"error": "Authenticated user is not an SME"}, status=status.HTTP_403_FORBIDDEN)
        return request.user, None

    # Otherwise, get sme_id from query params (or user_id)
    sme_id = request.GET.get("sme_id") or request.GET.get("user_id")
    if not sme_id:
        return None, Response(
            {"error": "sme_id is required when not authenticated"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Try to fetch the user with role sme
    try:
        user = User.objects.get(id=sme_id, role="sme")
    except User.DoesNotExist:
        return None, Response({"error": "Invalid sme_id"}, status=status.HTTP_404_NOT_FOUND)

    return user, None


# Helper to extract admin/staff user from request (authentication or query param)
def get_admin_user_from_request(request):
    # If authenticated user is staff or superuser, return it
    if getattr(request, "user", None) and request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return request.user, None
        return None, Response(
            {"error": "Authenticated user is not admin/staff"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Otherwise, get admin_id from query params
    admin_id = request.GET.get("admin_id") or request.GET.get("user_id")
    if not admin_id:
        return None, Response(
            {"error": "admin_id is required when not authenticated"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Fetch the user and check staff status
    try:
        admin_user = User.objects.get(id=admin_id)
    except User.DoesNotExist:
        return None, Response({"error": "Invalid admin_id"}, status=status.HTTP_404_NOT_FOUND)

    if not (admin_user.is_staff or admin_user.is_superuser):
        return None, Response(
            {"error": "Provided user is not admin/staff"},
            status=status.HTTP_403_FORBIDDEN,
        )

    return admin_user, None


# View to get admin dashboard analytics
class AdminStatsAPIView(SafeAPIView):
    def get(self, request):
        # Get admin user or error
        admin_user, error_response = get_admin_user_from_request(request)
        if error_response:
            return error_response

        # Gather statistics
        total_users = User.objects.count()
        total_loads = Load.objects.count()
        total_bookings = Booking.objects.count()
        total_driver_availability = Truck.objects.filter(driver__isnull=False).count()
        total_revenue = (
            Invoice.objects.filter(load__status="Completed").aggregate(total=Sum("cost")).get("total")
            or Decimal("0")
        )

        # Return the analytics
        return Response(
            {
                "admin_id": admin_user.id,
                "analytics": {
                    "total_users": total_users,
                    "total_loads": total_loads,
                    "total_bookings": total_bookings,
                    "total_driver_availability": total_driver_availability,
                    "total_revenue": total_revenue,
                },
            },
            status=status.HTTP_200_OK,
        )


# View to get SME dashboard summary (total bookings, active, completed)
class SMEDashboardAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user or error
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Get all loads for this SME
        shipments = Load.objects.filter(user=sme_user)
        # Build summary dictionary
        summary = {
            "total_bookings": shipments.count(),
            "active_shipments": shipments.filter(status__in=["Pre Pending", "Pending", "Accepted", "Picked"]).count(),
            "completed_shipments": shipments.filter(status="Completed").count(),
        }
        # Serialize and return
        serializer = SMEDashboardSummarySerializer(summary)
        return Response(serializer.data, status=status.HTTP_200_OK)


# View to list all shipments (loads) for the SME
class SMEShipmentsAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Get all loads for this SME, newest first, with driver
        shipments = (
            Load.objects.filter(user=sme_user)
            .select_related("driver")
            .order_by("-id")
        )
        # Serialize and return
        serializer = SMEShipmentSerializer(shipments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# View to list invoices for the SME
class SMEInvoicesAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Get invoices for this SME, include related booking/load/driver, newest first
        invoices = (
            Invoice.objects.filter(sme=sme_user)
            .select_related("booking", "load", "driver")
            .order_by("-id")
        )
        # Serialize and return
        serializer = SMEInvoiceSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# View to retrieve or update a specific invoice
class InvoiceDetailAPIView(SafeAPIView):
    def get(self, request, id):
        # Fetch the invoice with related data
        try:
            invoice = Invoice.objects.select_related("booking", "load", "driver", "sme", "load__truck").get(id=id)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

        # Optionally check SME ownership via query param
        sme_id = request.GET.get("sme_id")
        if sme_id and str(invoice.sme_id or "") != str(sme_id):
            return Response({"error": "Invoice does not belong to this SME"}, status=status.HTTP_403_FORBIDDEN)

        # Return serialized invoice
        return Response(SMEInvoiceSerializer(invoice).data, status=status.HTTP_200_OK)

    def patch(self, request, id):
        # Fetch the invoice (with sme)
        try:
            invoice = Invoice.objects.select_related("sme").get(id=id)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check ownership
        sme_id = request.GET.get("sme_id") or request.data.get("sme_id")
        if sme_id and str(invoice.sme_id or "") != str(sme_id):
            return Response({"error": "Invoice does not belong to this SME"}, status=status.HTTP_403_FORBIDDEN)

        # Get update fields from request
        payment_method = request.data.get("payment_method")
        payment_status = request.data.get("payment_status")
        transaction_id = request.data.get("transaction_id")

        # Validate payment_method
        if payment_method and payment_method not in {"cash", "online", "wallet"}:
            return Response({"error": "payment_method must be cash, online, or wallet"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate payment_status
        if payment_status and payment_status not in {"paid", "unpaid"}:
            return Response({"error": "payment_status must be paid or unpaid"}, status=status.HTTP_400_BAD_REQUEST)

        # Update fields
        if payment_method is not None:
            invoice.payment_method = payment_method
        if payment_status is not None:
            invoice.payment_status = payment_status
            invoice.paid = payment_status == "paid"
        elif request.data.get("paid") is not None:
            invoice.paid = bool(request.data.get("paid"))
            invoice.payment_status = "paid" if invoice.paid else "unpaid"

        if transaction_id is not None:
            invoice.transaction_id = transaction_id

        # Save only the changed fields
        invoice.save(update_fields=["payment_method", "payment_status", "paid", "transaction_id"])
        # Return updated invoice
        return Response(
            {
                "message": "Invoice updated successfully",
                "invoice": SMEInvoiceSerializer(invoice).data,
            },
            status=status.HTTP_200_OK,
        )


# View to generate a PDF for an invoice
class SMEInvoicePDFAPIView(SafeAPIView):
    def get(self, request, id):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Fetch the invoice for this SME
        try:
            invoice = Invoice.objects.select_related("sme", "driver", "load").get(id=id, sme=sme_user)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

        # Try to import reportlab for PDF generation
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except Exception:
            return Response(
                {"error": "PDF generation dependency is not installed (reportlab)."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        # Create an in-memory PDF
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        line_gap = 24

        # Write invoice details
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, y, f"Invoice #{invoice.id}")
        y -= line_gap * 2

        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, y, f"SME Name: {invoice.sme.first_name if invoice.sme else 'N/A'}")
        y -= line_gap
        pdf.drawString(50, y, f"Driver Name: {invoice.driver.first_name if invoice.driver else 'N/A'}")
        y -= line_gap
        pdf.drawString(50, y, f"Route: {invoice.route or 'N/A'}")
        y -= line_gap
        pdf.drawString(50, y, f"Cost: {invoice.cost if invoice.cost is not None else 'N/A'}")
        y -= line_gap
        pdf.drawString(50, y, f"Date: {invoice.date}")
        y -= line_gap
        pdf.drawString(50, y, f"Paid: {'Yes' if invoice.paid else 'No'}")

        # Save PDF to buffer
        pdf.showPage()
        pdf.save()
        buffer.seek(0)

        # Return as downloadable response
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice_{invoice.id}.pdf"'
        return response


# View to list completed loads as potential sources for repeat orders
class SMERepeatOrdersAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Get completed loads for this SME, newest first
        completed_loads = (
            Load.objects.filter(user=sme_user, status="Completed")
            .order_by("-id")
        )
        # Serialize using the repeat order source serializer
        serializer = SMERepeatOrderSourceSerializer(completed_loads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# View to create a new load based on a completed load (repeat order)
class CreateSMERepeatOrderAPIView(SafeAPIView):
    def post(self, request, id):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Fetch the completed load for this SME
        try:
            previous_load = Load.objects.get(id=id, user=sme_user, status="Completed")
        except Load.DoesNotExist:
            return Response(
                {"error": "Completed load not found for this SME"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Normalize the payload
        payload = normalize_route_payload(dict(request.data or {}))
        # Create a new load by copying fields from the previous load, optionally overriding with request data
        new_load = Load.objects.create(
            user=sme_user,
            created_by_role="sme",
            pickup_location=payload.get("pickup_location", previous_load.pickup_location),
            drop_location=payload.get("drop_location", previous_load.drop_location),
            pickup_address=payload.get("pickup_address", previous_load.pickup_address),
            drop_address=payload.get("drop_address", previous_load.drop_address),
            pickup_lat=payload.get("pickup_lat", previous_load.pickup_lat),
            pickup_lng=payload.get("pickup_lng", previous_load.pickup_lng),
            drop_lat=payload.get("drop_lat", previous_load.drop_lat),
            drop_lng=payload.get("drop_lng", previous_load.drop_lng),
            route_distance_km=payload.get("route_distance_km", previous_load.route_distance_km),
            route_duration_minutes=payload.get("route_duration_minutes", previous_load.route_duration_minutes),
            weight=previous_load.weight,
            load_type=previous_load.load_type,
            load_mode=previous_load.load_mode,
            budget_rate=previous_load.budget_rate,
            calculated_budget=previous_load.calculated_budget,
            final_budget=previous_load.final_budget or previous_load.budget_rate,
            status="Pending",
            driver=None,
            truck=None,
        )

        # Create a RepeatOrder record linking the previous load
        RepeatOrder.objects.create(
            user=sme_user,
            previous_load=previous_load,
        )

        # Return success
        return Response(
            {
                "message": "Repeat order created successfully",
                "previous_load_id": previous_load.id,
                "new_load": LoadSerializer(new_load).data,
            },
            status=status.HTTP_201_CREATED,
        )


# Helper to parse a route string into pickup and drop locations
def parse_scheduled_route(route_value):
    # If no route, return None, None
    if not route_value:
        return None, None

    route = str(route_value).strip()
    # Try splitting by "->"
    if "->" in route:
        pickup, drop = route.split("->", 1)
        return pickup.strip(), drop.strip()
    # Try splitting by " to " (case-insensitive)
    if " to " in route.lower():
        parts = route.split(" to ", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    # Try splitting by comma
    if "," in route:
        pickup, drop = route.split(",", 1)
        return pickup.strip(), drop.strip()

    # Otherwise return the whole string as pickup, None as drop
    return route, None


# Convert due scheduled pickups for a specific SME into loads
def convert_due_scheduled_pickups(sme_user):
    today = timezone.localdate()
    # Find scheduled pickups for this SME that are due (date <= today) and not yet converted
    due_pickups = ScheduledPickup.objects.filter(
        sme=sme_user,
        pickup_date__lte=today,
        is_converted=False,
    ).order_by("id")

    # Iterate each scheduled pickup
    for item in due_pickups:
        # Parse route into pickup and drop locations, with fallback to dedicated fields
        pickup_location, drop_location = parse_scheduled_route(item.route)
        pickup_location = item.pickup_location or pickup_location
        drop_location = item.drop_location or drop_location

        # Build pickup datetime
        pickup_dt = None
        if item.pickup_date and item.pickup_time:
            naive_dt = datetime.combine(item.pickup_date, item.pickup_time)
            if timezone.is_naive(naive_dt):
                pickup_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            else:
                pickup_dt = naive_dt

        # Create a new Load from the scheduled pickup
        created_load = Load.objects.create(
            user=sme_user,
            created_by_role="sme",
            is_scheduled=True,
            pickup_location=pickup_location,
            drop_location=drop_location,
            pickup_address=item.pickup_address,
            drop_address=item.drop_address,
            pickup_lat=item.pickup_lat,
            pickup_lng=item.pickup_lng,
            drop_lat=item.drop_lat,
            drop_lng=item.drop_lng,
            route_distance_km=item.route_distance_km,
            route_duration_minutes=item.route_duration_minutes,
            weight=item.weight,
            load_type=item.load_type,
            load_mode=item.load_mode or "Partial",
            budget_rate=item.final_budget,
            calculated_budget=item.calculated_budget,
            final_budget=item.final_budget,
            pickup_time=pickup_dt,
            status="Pending",
        )

        # Mark the scheduled pickup as converted and link the load
        item.is_converted = True
        item.converted_load = created_load
        item.save(update_fields=["is_converted", "converted_load"])


# Convert all due scheduled pickups across all SMEs (called before some views)
def convert_all_due_scheduled_pickups():
    # Get distinct sme_ids with due pickups
    sme_ids = (
        ScheduledPickup.objects.filter(
            is_converted=False,
            pickup_date__isnull=False,
            pickup_date__lte=timezone.localdate(),
        )
        .values_list("sme_id", flat=True)
        .distinct()
    )
    # For each sme_id, fetch the user and convert their pickups
    for sme_id in sme_ids:
        if not sme_id:
            continue
        try:
            sme_user = User.objects.get(id=sme_id)
        except User.DoesNotExist:
            continue
        convert_due_scheduled_pickups(sme_user)


# View to manage scheduled pickups for SMEs (list or create)
class SMESchedulePickupAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Convert any due pickups before listing
        convert_due_scheduled_pickups(sme_user)
        # Get all scheduled pickups for this SME, newest first
        pickups = ScheduledPickup.objects.filter(sme=sme_user).order_by("-id")
        serializer = ScheduledPickupSerializer(pickups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Normalize payload and map field names
        payload = normalize_route_payload(dict(request.data.copy()))
        if "date" in payload and "pickup_date" not in payload:
            payload["pickup_date"] = payload.get("date")
        if "time" in payload and "pickup_time" not in payload:
            payload["pickup_time"] = payload.get("time")
        if "type" in payload and "load_type" not in payload:
            payload["load_type"] = payload.get("type")
        if "mode" in payload and "load_mode" not in payload:
            payload["load_mode"] = payload.get("mode")
        if "pickup_address" not in payload and "pickup_location" in payload:
            payload["pickup_address"] = payload.get("pickup_location")
        if "drop_address" not in payload and "drop_location" in payload:
            payload["drop_address"] = payload.get("drop_location")
        if "route_distance" in payload and "route_distance_km" not in payload:
            payload["route_distance_km"] = payload.get("route_distance")
        if "route_duration" in payload and "route_duration_minutes" not in payload:
            payload["route_duration_minutes"] = payload.get("route_duration")

        # Deserialize and validate
        serializer = ScheduledPickupSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Resolve budgets
        pickup_validated = serializer.validated_data
        calculated_budget, final_budget, budget_error = resolve_and_validate_budget(
            pickup_validated.get("route_distance_km"),
            pickup_validated.get("weight"),
            payload.get("calculated_budget"),
            payload.get("final_budget"),
        )
        if budget_error:
            return Response({"error": budget_error}, status=status.HTTP_400_BAD_REQUEST)

        # Save the scheduled pickup
        pickup = serializer.save(
            sme=sme_user,
            calculated_budget=calculated_budget,
            final_budget=final_budget,
        )

        # Build pickup datetime
        pickup_dt = None
        if pickup.pickup_date and pickup.pickup_time:
            naive_dt = datetime.combine(pickup.pickup_date, pickup.pickup_time)
            pickup_dt = timezone.make_aware(naive_dt, timezone.get_current_timezone()) if timezone.is_naive(naive_dt) else naive_dt

        # Immediately create a load for this scheduled pickup
        created_load = Load.objects.create(
            user=sme_user,
            created_by_role="sme",
            is_scheduled=True,
            pickup_location=pickup.pickup_location,
            drop_location=pickup.drop_location,
            pickup_address=pickup.pickup_address,
            drop_address=pickup.drop_address,
            pickup_lat=pickup.pickup_lat,
            pickup_lng=pickup.pickup_lng,
            drop_lat=pickup.drop_lat,
            drop_lng=pickup.drop_lng,
            route_distance_km=pickup.route_distance_km,
            route_duration_minutes=pickup.route_duration_minutes,
            weight=pickup.weight,
            load_type=pickup.load_type,
            load_mode=pickup.load_mode or "Partial",
            budget_rate=final_budget,
            calculated_budget=calculated_budget,
            final_budget=final_budget,
            pickup_time=pickup_dt,
            status="Pending",
        )
        # Mark the scheduled pickup as converted
        pickup.is_converted = True
        pickup.converted_load = created_load
        pickup.save(update_fields=["is_converted", "converted_load"])

        # Return serialized scheduled pickup
        return Response(ScheduledPickupSerializer(pickup).data, status=status.HTTP_201_CREATED)


# View to manage bulk bookings for SMEs (list or create)
class SMEBulkBookingAPIView(SafeAPIView):
    def get(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Get all bulk bookings for this SME, prefetch items with their driver/truck/load, newest first
        queryset = (
            BulkBooking.objects.filter(sme=sme_user)
            .prefetch_related("items__driver", "items__truck", "items__load")
            .order_by("-id")
        )
        # Serialize and return
        serializer = BulkBookingSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Normalize payload
        payload = normalize_route_payload(dict(request.data or {}))
        serializer = BulkBookingCreateSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        weights = validated["weights"]
        calculated_budgets = validated.get("calculated_budgets")
        final_budgets = validated.get("final_budgets")
        route_distance_km = validated.get("route_distance_km")

        # Resolve budgets for each weight item
        resolved_calculated_budgets = []
        resolved_final_budgets = []
        for index, weight in enumerate(weights):
            calc_input = calculated_budgets[index] if calculated_budgets is not None else None
            final_input = final_budgets[index] if final_budgets is not None else None
            calc_budget, final_budget, budget_error = resolve_and_validate_budget(
                route_distance_km,
                weight,
                calc_input,
                final_input,
            )
            if budget_error:
                return Response(
                    {"error": f"Item {index + 1}: {budget_error}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved_calculated_budgets.append(calc_budget)
            resolved_final_budgets.append(final_budget)

        # Create bulk booking and related loads within a transaction
        with transaction.atomic():
            bulk_booking = BulkBooking.objects.create(
                sme=sme_user,
                number_of_loads=validated.get("number_of_loads") or len(weights),
                route=validated["route"],
                pickup_location=validated.get("pickup_location"),
                drop_location=validated.get("drop_location"),
                pickup_address=validated.get("pickup_address"),
                drop_address=validated.get("drop_address"),
                pickup_lat=validated.get("pickup_lat"),
                pickup_lng=validated.get("pickup_lng"),
                drop_lat=validated.get("drop_lat"),
                drop_lng=validated.get("drop_lng"),
                route_distance_km=validated.get("route_distance_km"),
                route_duration_minutes=validated.get("route_duration_minutes"),
            )
            # Create individual loads for each weight
            for index, weight in enumerate(weights):
                load = Load.objects.create(
                    user=sme_user,
                    created_by_role="sme",
                    is_scheduled=False,
                    bulk_booking=bulk_booking,
                    pickup_location=bulk_booking.pickup_location,
                    drop_location=bulk_booking.drop_location,
                    pickup_address=bulk_booking.pickup_address,
                    drop_address=bulk_booking.drop_address,
                    pickup_lat=bulk_booking.pickup_lat,
                    pickup_lng=bulk_booking.pickup_lng,
                    drop_lat=bulk_booking.drop_lat,
                    drop_lng=bulk_booking.drop_lng,
                    route_distance_km=bulk_booking.route_distance_km,
                    route_duration_minutes=bulk_booking.route_duration_minutes,
                    weight=weight,
                    load_type="Normal",
                    load_mode="Partial",
                    budget_rate=resolved_final_budgets[index],
                    calculated_budget=resolved_calculated_budgets[index],
                    final_budget=resolved_final_budgets[index],
                    status="Pending",
                )
                # Create a BulkBookingItem linking to the load
                BulkBookingItem.objects.create(
                    bulk_booking=bulk_booking,
                    weight=weight,
                    calculated_budget=resolved_calculated_budgets[index],
                    final_budget=resolved_final_budgets[index],
                    load=load,
                    status="Pending",
                )

        # Return success with serialized bulk booking
        return Response(
            {
                "message": "Bulk booking created successfully",
                "bulk_booking": BulkBookingSerializer(bulk_booking).data,
            },
            status=status.HTTP_201_CREATED,
        )


# Helper to retrieve a pool of available trucks with their remaining capacity, optionally filtered by route
def get_driver_capacity_pool(pickup_city=None, drop_city=None):
    pool = []
    # Get all trucks with drivers, newest first
    trucks = get_truck_queryset().select_related("driver").filter(driver__isnull=False).order_by("-id")
    for truck in trucks:
        # Skip if driver not found or role is not driver
        if not truck.driver or truck.driver.role != "driver":
            continue
        # Skip if availability not posted
        if not is_truck_availability_posted(truck):
            continue
        # Skip if route does not match (if provided)
        if not truck_matches_route(truck, pickup_city, drop_city):
            continue
        # Get remaining capacity
        capacity = get_remaining_capacity(truck)
        # If no capacity, skip
        if capacity <= 0:
            continue
        # Add to pool
        pool.append(
            {
                "truck": truck,
                "driver": truck.driver,
                "capacity": capacity,
            }
        )
    return pool


# View to automatically assign drivers to bulk booking items based on available capacity pool
class SMEBulkBookingAutoAssignAPIView(SafeAPIView):
    def post(self, request, id):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Fetch the bulk booking with items
        try:
            bulk_booking = BulkBooking.objects.prefetch_related("items").get(id=id, sme=sme_user)
        except BulkBooking.DoesNotExist:
            return Response({"error": "Bulk booking not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get pending items sorted by weight descending
        pending_items = list(
            bulk_booking.items.filter(status="Pending").order_by("-weight", "id")
        )
        if not pending_items:
            return Response(
                {"message": "All bulk booking items are already assigned"},
                status=status.HTTP_200_OK,
            )

        # Determine route details
        pickup_location, drop_location = parse_scheduled_route(bulk_booking.route)
        pickup_location = bulk_booking.pickup_location or pickup_location
        drop_location = bulk_booking.drop_location or drop_location
        # Build capacity pool
        capacity_pool = get_driver_capacity_pool(pickup_location, drop_location)
        if not capacity_pool:
            return Response(
                {"error": "No available drivers/trucks found for assignment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assigned_item_ids = []
        unassigned_item_ids = []

        # Process assignments in a transaction
        with transaction.atomic():
            for item in pending_items:
                item_weight = normalize_decimal(item.weight)
                # Find a truck with enough capacity
                assigned_entry = next(
                    (entry for entry in capacity_pool if item_weight > 0 and entry["capacity"] >= item_weight),
                    None,
                )
                if not assigned_entry:
                    unassigned_item_ids.append(item.id)
                    continue

                load = item.load
                if not load:
                    unassigned_item_ids.append(item.id)
                    continue

                # Update load fields (ensure it's assigned to SME, etc.)
                load.user = sme_user
                load.created_by_role = "sme"
                load.pickup_location = pickup_location
                load.drop_location = drop_location
                load.pickup_address = bulk_booking.pickup_address
                load.drop_address = bulk_booking.drop_address
                load.pickup_lat = bulk_booking.pickup_lat
                load.pickup_lng = bulk_booking.pickup_lng
                load.drop_lat = bulk_booking.drop_lat
                load.drop_lng = bulk_booking.drop_lng
                load.route_distance_km = bulk_booking.route_distance_km
                load.route_duration_minutes = bulk_booking.route_duration_minutes
                load.weight = item.weight
                load.load_type = load.load_type or "Normal"
                load.load_mode = load.load_mode or "Partial"
                load.status = "Pre Pending"
                load.driver = assigned_entry["driver"]
                load.truck = assigned_entry["truck"]
                load.save()

                # Update the bulk booking item
                item.driver = assigned_entry["driver"]
                item.truck = assigned_entry["truck"]
                item.status = "Assigned"
                item.save(update_fields=["driver", "truck", "status"])
                assigned_item_ids.append(item.id)

        # Return assignment results
        return Response(
            {
                "message": "Auto assignment completed",
                "bulk_booking_id": bulk_booking.id,
                "assigned_item_ids": assigned_item_ids,
                "unassigned_item_ids": unassigned_item_ids,
                "bulk_booking": BulkBookingSerializer(BulkBooking.objects.get(id=bulk_booking.id)).data,
            },
            status=status.HTTP_200_OK,
        )


# View to track a specific shipment (load) with status history and driver location
class TrackShipmentAPIView(SafeAPIView):
    def get(self, request, load_id):
        # Get SME user
        sme_user, error_response = get_sme_user_from_request(request)
        if error_response:
            return error_response

        # Fetch the load with driver
        try:
            load = Load.objects.select_related("driver").get(id=load_id)
        except Load.DoesNotExist:
            return Response({"error": "Load not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the load belongs to this SME
        if load.user_id != sme_user.id:
            return Response(
                {"error": "This shipment does not belong to this SME"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get status history for the load
        history = LoadStatusHistory.objects.filter(load=load).order_by("timestamp")
        history_data = LoadStatusHistorySerializer(history, many=True).data

        # Get driver's current location if available
        driver_location = None
        if load.driver_current_latitude is not None and load.driver_current_longitude is not None:
            driver_location = {
                "latitude": load.driver_current_latitude,
                "longitude": load.driver_current_longitude,
                "updated_at": load.driver_location_updated_at,
            }

        # Return detailed tracking info
        return Response(
            {
                "load_id": load.id,
                "load_status": load.status,
                "driver": {
                    "id": load.driver.id,
                    "name": load.driver.first_name,
                    "phone": load.driver.phone_number,
                } if load.driver else None,
                "current_driver_location": driver_location,
                "pickup": {
                    "location": load.pickup_location,
                    "address": load.pickup_address,
                    "latitude": load.pickup_lat,
                    "longitude": load.pickup_lng,
                },
                "drop": {
                    "location": load.drop_location,
                    "address": load.drop_address,
                    "latitude": load.drop_lat,
                    "longitude": load.drop_lng,
                },
                "route_distance_km": load.route_distance_km,
                "route_duration_minutes": load.route_duration_minutes,
                "history": history_data,
                "allowed_flow": "Pending -> Accepted -> Picked -> Completed",
            },
            status=status.HTTP_200_OK,
        )