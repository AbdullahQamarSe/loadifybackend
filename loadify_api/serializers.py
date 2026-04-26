# Import Decimal for precise decimal number handling and ROUND_HALF_UP for rounding
from decimal import Decimal, ROUND_HALF_UP
# Import authenticate for user authentication functionality
from django.contrib.auth import authenticate
# Import transaction for database transaction management
from django.db import transaction
# Import serializers from Django REST Framework for API serialization
from rest_framework import serializers

# Import all the database models needed for serialization
from .models import (
    BulkBooking,        # Model for bulk booking records
    BulkBookingItem,     # Model for individual items in bulk booking
    Invoice,            # Model for invoice records
    Load,                # Model for load/shipment records
    LoadStatusHistory,   # Model for tracking load status changes
    ScheduledPickup,     # Model for scheduled pickup records
    Truck,               # Model for truck information
    User,                # Custom user model
)


def clamp_decimal(value, max_abs=None, max_total=None, decimal_places=2):
    """
    Clamp a Decimal value to safe limits and round to given decimal_places.
    - max_abs: absolute maximum (e.g., for lat/lng)
    - max_total: maximum total number (e.g., for distance/weight)
    """
    # Return None if the input value is None
    if value is None:
        return None
    # Check if the value is not already a Decimal instance
    if not isinstance(value, Decimal):
        try:
            # Try to convert the value to Decimal using string representation
            value = Decimal(str(value))
        except Exception:
            # Return None if conversion fails
            return None

    # Apply absolute clamp if provided (for coordinates like lat/lng)
    if max_abs is not None:
        # If value exceeds maximum absolute value, clamp it to max_abs
        if value > max_abs:
            value = max_abs
        # If value is below negative maximum, clamp it to -max_abs
        elif value < -max_abs:
            value = -max_abs

    # Apply total value clamp (e.g., for distance, weight, budget - 9,999,999.99)
    if max_total is not None:
        # If value exceeds maximum total, clamp it to max_total
        if value > max_total:
            value = max_total
        # If value is below negative maximum, clamp it to -max_total
        elif value < -max_total:
            value = -max_total

    # Round to the required decimal places using proper quantizer
    quantizer = Decimal('1') / Decimal(10 ** decimal_places)
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


class LoginSerializer(serializers.Serializer):
    # Email field for user login - validates email format
    email = serializers.EmailField()
    # Password field for user login - handles secure password input
    password = serializers.CharField()

    def validate(self, data):
        # Extract email from the validated data
        email = data.get("email")
        # Extract password from the validated data
        password = data.get("password")

        try:
            # Try to find user by email address
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            # Raise validation error if user doesn't exist
            raise serializers.ValidationError("Invalid email or password") from exc

        # Authenticate user with username and password
        user = authenticate(username=user.username, password=password)

        # If authentication fails, raise validation error
        if not user:
            raise serializers.ValidationError("Invalid email or password")

        # Add authenticated user to the data dictionary
        data["user"] = user
        # Return the validated data with user object
        return data


class RegisterSerializer(serializers.Serializer):
    # Role field - determines user type (trader, driver, sme)
    role = serializers.CharField()
    # Name field - user's full name
    name = serializers.CharField()
    # Phone field - user's phone number
    phone = serializers.CharField()
    # Email field - user's email address with validation
    email = serializers.EmailField()
    # Password field - user's password
    password = serializers.CharField()

    # City field - user's city (optional)
    city = serializers.CharField(required=False, allow_blank=True)

    # Trader specific fields
    # Goods type - type of goods the trader deals with
    goodsType = serializers.CharField(required=False, allow_blank=True)

    # Driver specific fields
    # CNIC - national identity card number for driver
    cnic = serializers.CharField(required=False, allow_blank=True)
    # Truck type - type of truck the driver owns
    truckType = serializers.CharField(required=False, allow_blank=True)
    # Truck registration - truck registration number
    truckReg = serializers.CharField(required=False, allow_blank=True)
    # Capacity - truck capacity in tons
    capacity = serializers.CharField(required=False, allow_blank=True)

    # SME (Small Medium Enterprise) specific fields
    # Business name - name of the SME business
    businessName = serializers.CharField(required=False, allow_blank=True)
    # Business type - type of business
    businessType = serializers.CharField(required=False, allow_blank=True)
    # NTN - National Tax Number for the business
    ntn = serializers.CharField(required=False, allow_blank=True)
    # Owner name - name of the business owner
    ownerName = serializers.CharField(required=False, allow_blank=True)
    # Business email - business contact email
    businessEmail = serializers.EmailField(required=False, allow_blank=True)
    # Address - business address
    address = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        # Check if a user with this email already exists (case-insensitive)
        if User.objects.filter(email__iexact=value).exists():
            # Raise validation error if email is already taken
            raise serializers.ValidationError("An account with this email already exists.")
        # Return the validated email value
        return value

    def validate(self, data):
        # Extract the role from the validated data
        role = data.get("role")

        # Validate that the role is one of the allowed options
        if role not in {"trader", "driver", "sme"}:
            # Raise validation error if role is invalid
            raise serializers.ValidationError({"role": "Invalid role selected."})

        # If the role is driver, validate required driver fields
        if role == "driver":
            # Find missing required driver fields
            missing = [
                field for field in ("cnic", "truckType", "truckReg", "capacity")
                if not data.get(field)
            ]
            # If any required fields are missing, raise validation error
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required for drivers." for field in missing}
                )

        # If the role is SME, validate required SME fields
        if role == "sme":
            # Find missing required SME fields
            missing = [
                field for field in ("businessName", "businessType", "address")
                if not data.get(field)
            ]
            # If any required fields are missing, raise validation error
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required for SMEs." for field in missing}
                )

        # Return the validated data
        return data

    def create(self, validated_data):
        # Extract the role from validated data
        role = validated_data.get("role")

        try:
            # Use database transaction to ensure atomicity
            with transaction.atomic():
                # Create the user account with all the provided data
                user = User.objects.create_user(
                    username=validated_data["email"],           # Use email as username
                    email=validated_data["email"],              # Set email address
                    password=validated_data["password"],         # Set password
                    first_name=validated_data["name"],           # Set user's name
                    phone_number=validated_data["phone"],        # Set phone number
                    role=role,                                    # Set user role
                    city=validated_data.get("city"),             # Set city (optional)
                    goods_type=validated_data.get("goodsType"),   # Set goods type (for traders)
                    cnic=validated_data.get("cnic"),               # Set CNIC (for drivers)
                    business_name=validated_data.get("businessName"),  # Set business name (for SMEs)
                    business_type=validated_data.get("businessType"),  # Set business type (for SMEs)
                    ntn=validated_data.get("ntn"),                 # Set NTN (for SMEs)
                    owner_name=validated_data.get("ownerName"),    # Set owner name (for SMEs)
                    business_email=validated_data.get("businessEmail"), # Set business email (for SMEs)
                    business_address=validated_data.get("address"),    # Set business address (for SMEs)
                )

                # If the role is driver, create associated truck record
                if role == "driver":
                    Truck.objects.create(
                        driver=user,                                   # Link truck to the user
                        truck_type=validated_data.get("truckType"),   # Set truck type
                        registration_no=validated_data.get("truckReg"), # Set registration number
                        total_capacity=validated_data.get("capacity"), # Set total capacity
                        used_capacity="0",                           # Initialize used capacity to 0
                        remaining_capacity=validated_data.get("capacity"), # Set remaining capacity
                        available_capacity=validated_data.get("capacity"), # Set available capacity
                    )

                # Return the created user object
                return user
        except Exception as exc:
            # Print error for debugging purposes
            print(f"Registration failed after user creation: {exc}")
            # Raise validation error with exception details
            raise serializers.ValidationError({"detail": str(exc)}) from exc


class LoadSerializer(serializers.ModelSerializer):
    class Meta:
        # Specify the model to serialize
        model = Load
        # Include all fields from the model
        fields = "__all__"
        # Make user and status fields read-only (they should be set programmatically)
        read_only_fields = ["user", "status"]


class SMEDashboardSummarySerializer(serializers.Serializer):
    # Total number of bookings for the SME
    total_bookings = serializers.IntegerField()
    # Number of active/ongoing shipments
    active_shipments = serializers.IntegerField()
    # Number of completed shipments
    completed_shipments = serializers.IntegerField()


class SMEShipmentSerializer(serializers.ModelSerializer):
    # Custom field to get driver information
    driver = serializers.SerializerMethodField()

    class Meta:
        # Specify the model to serialize
        model = Load
        # Define the fields to include in the serialization
        fields = [
            "id",                    # Load ID
            "pickup_location",       # Pickup location name
            "drop_location",         # Drop location name
            "pickup_address",        # Detailed pickup address
            "drop_address",          # Detailed drop address
            "pickup_lat",            # Pickup latitude coordinate
            "pickup_lng",            # Pickup longitude coordinate
            "drop_lat",              # Drop latitude coordinate
            "drop_lng",              # Drop longitude coordinate
            "route_distance_km",     # Route distance in kilometers
            "route_duration_minutes", # Route duration in minutes
            "weight",                # Load weight
            "load_type",             # Type of load (Fragile/Normal)
            "load_mode",             # Load mode (Full/Partial)
            "budget_rate",           # Budget rate per unit
            "pickup_time",           # Scheduled pickup time
            "status",                # Current load status
            "driver",                # Driver information (custom field)
        ]

    def get_driver(self, obj):
        # Custom method to get driver information
        if not obj.driver:
            # Return None if no driver is assigned
            return None
        # Return driver details as a dictionary
        return {
            "id": obj.driver.id,                    # Driver ID
            "name": obj.driver.first_name,           # Driver name
            "phone": obj.driver.phone_number,        # Driver phone number
            "email": obj.driver.email,               # Driver email
        }


class SMEInvoiceSerializer(serializers.ModelSerializer):
    # Booking ID from related booking object (read-only)
    booking_id = serializers.IntegerField(source="booking.id", read_only=True)
    # Load ID from related load object (read-only)
    load_id = serializers.IntegerField(source="load.id", read_only=True)
    # Custom field to get driver information
    driver = serializers.SerializerMethodField()
    # SME name from related user object (read-only)
    sme_name = serializers.CharField(source="sme.first_name", read_only=True)
    # Driver name from related user object (read-only)
    driver_name = serializers.CharField(source="driver.first_name", read_only=True)
    # Route distance from related load object (read-only, decimal with 10 digits, 2 decimal places)
    route_distance_km = serializers.DecimalField(
        source="load.route_distance_km",  # Source field from load model
        max_digits=10,                    # Maximum total digits allowed
        decimal_places=2,                 # Number of decimal places
        read_only=True,                    # Read-only field
        allow_null=True,                   # Allow null values
    )
    # Route duration from related load object (read-only, integer)
    route_duration_minutes = serializers.IntegerField(
        source="load.route_duration_minutes",  # Source field from load model
        read_only=True,                        # Read-only field
        allow_null=True,                       # Allow null values
    )
    # Truck registration number from related load's truck (read-only)
    truck_registration_no = serializers.CharField(source="load.truck.registration_no", read_only=True)
    # Truck type from related load's truck (read-only)
    truck_type = serializers.CharField(source="load.truck.truck_type", read_only=True)
    # Pickup location from related load object (read-only)
    pickup_location = serializers.CharField(source="load.pickup_location", read_only=True)
    # Drop location from related load object (read-only)
    drop_location = serializers.CharField(source="load.drop_location", read_only=True)

    class Meta:
        # Specify the model to serialize
        model = Invoice
        # Define the fields to include in the serialization
        fields = [
            "id",                    # Invoice ID
            "sme_name",              # SME name
            "driver_name",           # Driver name
            "load_id",               # Load ID
            "booking_id",            # Booking ID
            "route",                 # Route description
            "pickup_location",       # Pickup location
            "drop_location",         # Drop location
            "route_distance_km",     # Route distance in kilometers
            "route_duration_minutes", # Route duration in minutes
            "cost",                  # Invoice cost
            "paid",                  # Amount paid
            "payment_status",        # Payment status
            "payment_method",        # Payment method used
            "transaction_id",         # Transaction ID
            "truck_registration_no", # Truck registration number
            "truck_type",            # Truck type
            "date",                  # Invoice date
            "driver",                # Driver information (custom field)
        ]

    def get_driver(self, obj):
        # Custom method to get driver information
        if not obj.driver:
            # Return None if no driver is assigned
            return None
        # Return driver details as a dictionary
        return {
            "id": obj.driver.id,                    # Driver ID
            "name": obj.driver.first_name,           # Driver name
            "phone": obj.driver.phone_number,        # Driver phone number
            "email": obj.driver.email,               # Driver email
        }


class SMERepeatOrderSourceSerializer(serializers.ModelSerializer):
    class Meta:
        # Specify the model to serialize (Load model for repeat orders)
        model = Load
        # Define the fields to include in the serialization for repeat order source
        fields = [
            "id",                    # Load ID
            "pickup_location",       # Pickup location name
            "drop_location",         # Drop location name
            "pickup_address",        # Detailed pickup address
            "drop_address",          # Detailed drop address
            "pickup_lat",            # Pickup latitude coordinate
            "pickup_lng",            # Pickup longitude coordinate
            "drop_lat",              # Drop latitude coordinate
            "drop_lng",              # Drop longitude coordinate
            "route_distance_km",     # Route distance in kilometers
            "route_duration_minutes", # Route duration in minutes
            "weight",                # Load weight
            "load_type",             # Type of load (Fragile/Normal)
            "load_mode",             # Load mode (Full/Partial)
            "status",                # Current load status
        ]


class ScheduledPickupSerializer(serializers.ModelSerializer):
    class Meta:
        # Specify the model to serialize (ScheduledPickup model)
        model = ScheduledPickup
        # Define the fields to include in the serialization
        fields = [
            "id",                    # Scheduled pickup ID
            "pickup_date",           # Scheduled pickup date
            "pickup_time",           # Scheduled pickup time
            "route",                 # Route description
            "pickup_location",       # Pickup location name
            "drop_location",         # Drop location name
            "pickup_address",        # Detailed pickup address
            "drop_address",          # Detailed drop address
            "pickup_lat",            # Pickup latitude coordinate
            "pickup_lng",            # Pickup longitude coordinate
            "drop_lat",              # Drop latitude coordinate
            "drop_lng",              # Drop longitude coordinate
            "route_distance_km",     # Route distance in kilometers
            "route_duration_minutes", # Route duration in minutes
            "calculated_budget",     # Calculated budget for the pickup
            "final_budget",          # Final budget after negotiations
            "weight",                # Load weight
            "load_type",             # Type of load (Fragile/Normal)
            "load_mode",             # Load mode (Full/Partial)
            "is_converted",          # Whether pickup has been converted to load
            "converted_load",         # Reference to the converted load
        ]
        # Make is_converted and converted_load read-only (set programmatically)
        read_only_fields = ["is_converted", "converted_load"]

    def validate(self, data):
        """
        Sanitize decimal fields to avoid 'max_digits=10' errors.
        - Latitude: clamp to [-90, 90], round to 7 decimal places.
        - Longitude: clamp to [-180, 180], round to 7 decimal places.
        - Distance/weight/budgets: clamp to ±9,999,999.99, round to 2 decimal places.
        """
        # Define latitude fields that need coordinate validation (7 decimal places)
        lat_fields = ['pickup_lat', 'drop_lat']
        # Define longitude fields that need coordinate validation (7 decimal places)
        lng_fields = ['pickup_lng', 'drop_lng']

        # Process latitude fields - clamp to valid range [-90, 90]
        for field in lat_fields:
            if field in data and data[field] is not None:
                # Clamp latitude to [-90, 90] and round to 7 decimal places
                data[field] = clamp_decimal(data[field], max_abs=Decimal('90'), decimal_places=7)

        # Process longitude fields - clamp to valid range [-180, 180]
        for field in lng_fields:
            if field in data and data[field] is not None:
                # Clamp longitude to [-180, 180] and round to 7 decimal places
                data[field] = clamp_decimal(data[field], max_abs=Decimal('180'), decimal_places=7)

        # Define fields with 2 decimal places that need value clamping
        decimal_2_fields = ['route_distance_km', 'weight', 'calculated_budget', 'final_budget']
        # Process decimal fields with 2 decimal places
        for field in decimal_2_fields:
            if field in data and data[field] is not None:
                # Max total digits = 10, with 2 decimal places => max integer part = 8 digits => 99,999,999.99
                # But we use a safer realistic cap: 9,999,999.99 (7 integer digits)
                data[field] = clamp_decimal(data[field], max_total=Decimal('9999999.99'), decimal_places=2)

        # Return the validated and sanitized data
        return data


class BulkBookingItemSerializer(serializers.ModelSerializer):
    # Driver name from related driver object (read-only)
    driver_name = serializers.CharField(source="driver.first_name", read_only=True)
    # Truck registration number from related truck object (read-only)
    truck_registration_no = serializers.CharField(source="truck.registration_no", read_only=True)
    # Load ID from related load object (read-only)
    load_id = serializers.IntegerField(source="load.id", read_only=True)

    class Meta:
        # Specify the model to serialize (BulkBookingItem model)
        model = BulkBookingItem
        # Define the fields to include in the serialization
        fields = [
            "id",                    # Bulk booking item ID
            "weight",                # Item weight
            "calculated_budget",     # Calculated budget for this item
            "final_budget",          # Final budget for this item
            "status",                # Item status (Pending, Assigned, etc.)
            "driver",                # Assigned driver
            "driver_name",           # Driver name (custom field)
            "truck",                 # Assigned truck
            "truck_registration_no", # Truck registration number (custom field)
            "load_id",               # Related load ID (custom field)
        ]


class BulkBookingSerializer(serializers.ModelSerializer):
    # Nested serializer for bulk booking items (many items, read-only)
    items = BulkBookingItemSerializer(many=True, read_only=True)
    # SME name from related user object (read-only)
    sme_name = serializers.CharField(source="sme.first_name", read_only=True)

    class Meta:
        # Specify the model to serialize (BulkBooking model)
        model = BulkBooking
        # Define the fields to include in the serialization
        fields = [
            "id",                    # Bulk booking ID
            "sme",                   # SME user who created the booking
            "sme_name",              # SME name (custom field)
            "number_of_loads",       # Number of loads in this booking
            "route",                 # Route description
            "pickup_location",       # Pickup location name
            "drop_location",         # Drop location name
            "pickup_address",        # Detailed pickup address
            "drop_address",          # Detailed drop address
            "pickup_lat",            # Pickup latitude coordinate
            "pickup_lng",            # Pickup longitude coordinate
            "drop_lat",              # Drop latitude coordinate
            "drop_lng",              # Drop longitude coordinate
            "route_distance_km",     # Route distance in kilometers
            "route_duration_minutes", # Route duration in minutes
            "created_at",            # Creation timestamp
            "items",                 # Bulk booking items (nested serializer)
        ]


class BulkBookingCreateSerializer(serializers.Serializer):
    # Number of loads in the bulk booking (optional, minimum 1)
    number_of_loads = serializers.IntegerField(required=False, min_value=1)
    # Route description (required, max 200 characters)
    route = serializers.CharField(max_length=200)
    # Pickup location name (optional, max 100 characters, can be blank)
    pickup_location = serializers.CharField(max_length=100, required=False, allow_blank=True)
    # Drop location name (optional, max 100 characters, can be blank)
    drop_location = serializers.CharField(max_length=100, required=False, allow_blank=True)
    # Detailed pickup address (optional, can be blank)
    pickup_address = serializers.CharField(required=False, allow_blank=True)
    # Detailed drop address (optional, can be blank)
    drop_address = serializers.CharField(required=False, allow_blank=True)
    # Pickup latitude coordinate (optional, 10 total digits, 7 decimal places)
    pickup_lat = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    # Pickup longitude coordinate (optional, 10 total digits, 7 decimal places)
    pickup_lng = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    # Drop latitude coordinate (optional, 10 total digits, 7 decimal places)
    drop_lat = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    # Drop longitude coordinate (optional, 10 total digits, 7 decimal places)
    drop_lng = serializers.DecimalField(max_digits=10, decimal_places=7, required=False)
    # Route distance in kilometers (optional, 10 total digits, 2 decimal places)
    route_distance_km = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    # Route duration in minutes (optional, minimum 0)
    route_duration_minutes = serializers.IntegerField(required=False, min_value=0)
    # List of weights for each load (required, 15 total digits, 2 decimal places, minimum 0.01)
    weights = serializers.ListField(
        child=serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0.01),
        allow_empty=False,  # Cannot be empty
    )
    # List of calculated budgets for each load (optional, 15 total digits, 2 decimal places, minimum 0)
    calculated_budgets = serializers.ListField(
        child=serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0),
        required=False,     # Optional field
        allow_empty=False,  # Cannot be empty if provided
    )
    # List of final budgets for each load (optional, 15 total digits, 2 decimal places, minimum 0)
    final_budgets = serializers.ListField(
        child=serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0),
        required=False,     # Optional field
        allow_empty=False,  # Cannot be empty if provided
    )

    def validate(self, attrs):
        # Sanitize coordinate fields (if provided) to prevent validation errors
        lat_fields = ['pickup_lat', 'drop_lat']  # Latitude fields to validate
        lng_fields = ['pickup_lng', 'drop_lng']  # Longitude fields to validate

        # Process latitude fields - clamp to valid range [-90, 90]
        for field in lat_fields:
            if field in attrs and attrs[field] is not None:
                # Clamp latitude to [-90, 90] and round to 7 decimal places
                attrs[field] = clamp_decimal(attrs[field], max_abs=Decimal('90'), decimal_places=7)

        # Process longitude fields - clamp to valid range [-180, 180]
        for field in lng_fields:
            if field in attrs and attrs[field] is not None:
                # Clamp longitude to [-180, 180] and round to 7 decimal places
                attrs[field] = clamp_decimal(attrs[field], max_abs=Decimal('180'), decimal_places=7)

        # Sanitize route_distance_km to prevent 'max_digits' errors
        if 'route_distance_km' in attrs and attrs['route_distance_km'] is not None:
            # Clamp route distance to realistic maximum and round to 2 decimal places
            attrs['route_distance_km'] = clamp_decimal(attrs['route_distance_km'], max_total=Decimal('9999999.99'), decimal_places=2)

        # Validate count consistency between different arrays
        number_of_loads = attrs.get("number_of_loads")      # Number of loads specified
        weights = attrs.get("weights", [])                  # List of weights
        calculated_budgets = attrs.get("calculated_budgets") # List of calculated budgets
        final_budgets = attrs.get("final_budgets")          # List of final budgets

        # Validate that number_of_loads matches weights count if specified
        if number_of_loads is not None and number_of_loads != len(weights):
            raise serializers.ValidationError(
                {"number_of_loads": "number_of_loads must match weights count."}
            )
        # Validate that calculated_budgets count matches weights count if provided
        if calculated_budgets is not None and len(calculated_budgets) != len(weights):
            raise serializers.ValidationError(
                {"calculated_budgets": "calculated_budgets must match weights count."}
            )
        # Validate that final_budgets count matches weights count if provided
        if final_budgets is not None and len(final_budgets) != len(weights):
            raise serializers.ValidationError(
                {"final_budgets": "final_budgets must match weights count."}
            )
        # Validate that final budgets are not lower than calculated budgets
        if calculated_budgets is not None and final_budgets is not None:
            # Compare each calculated budget with its corresponding final budget
            for index, (calc_value, final_value) in enumerate(zip(calculated_budgets, final_budgets), start=1):
                if final_value < calc_value:
                    # Raise error if final budget is lower than calculated budget
                    raise serializers.ValidationError(
                        {"final_budgets": f"Item {index}: final budget cannot be lower than calculated budget."}
                    )
        # Return the validated and sanitized attributes
        return attrs


class LoadStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        # Specify the model to serialize (LoadStatusHistory model)
        model = LoadStatusHistory
        # Define the fields to include in the serialization
        fields = [
            "status",     # Load status at this point in time
            "timestamp",  # When this status change occurred
            "location",   # Location where status change happened (optional)
        ]