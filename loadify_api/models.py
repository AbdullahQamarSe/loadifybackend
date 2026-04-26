# Import Django's models module for database model definitions
from django.db import models
# Import AbstractUser to extend Django's built-in User model
from django.contrib.auth.models import AbstractUser
# Import Decimal for precise decimal number handling
from decimal import Decimal
# Import ValidationError for custom validation error handling
from django.core.exceptions import ValidationError
# Import transaction for database transaction management
from django.db import transaction


# ---------------------------
# USER MODEL
# ---------------------------
class User(AbstractUser):
    # Define the available user roles in the system
    ROLE_CHOICES = (
        ('trader', 'Trader'),  # User who posts loads for transport
        ('driver', 'Driver'),  # User who provides transportation services
        ('sme', 'SME'),        # Small/Medium Enterprise user
    )

    # User role field - determines what the user can do in the system
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, blank=True, null=True)

    # Contact information fields
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # User's phone number
    city = models.CharField(max_length=50, blank=True, null=True)           # User's city

    # Trader specific fields
    goods_type = models.CharField(max_length=100, blank=True, null=True)   # Type of goods trader deals with

    # Driver specific fields
    cnic = models.CharField(max_length=50, blank=True, null=True)           # National Identity Card number

    # SME (Small/Medium Enterprise) specific fields
    business_name = models.CharField(max_length=100, blank=True, null=True)    # Name of the business
    business_type = models.CharField(max_length=100, blank=True, null=True)    # Type of business
    ntn = models.CharField(max_length=50, blank=True, null=True)                # National Tax Number
    owner_name = models.CharField(max_length=100, blank=True, null=True)        # Name of business owner
    business_email = models.EmailField(blank=True, null=True)                    # Business contact email
    business_address = models.TextField(blank=True, null=True)                   # Business address

    def __str__(self):
        # String representation of the user object
        return f"{self.username} ({self.role})"


# ---------------------------
# TRUCK MODEL
# ---------------------------
class Truck(models.Model):
    # Define the available truck types in the system
    TRUCK_TYPE_CHOICES = (
        ('Shehzore', 'Shehzore'),    # Small pickup truck
        ('Mazda', 'Mazda'),          # Medium truck
        ('10-wheeler', '10-wheeler'), # Large truck with 10 wheels
    )

    # Define the available truck sizes
    SIZE_CHOICES = (
        ('Small', 'Small'),          # Small size truck
        ('Medium', 'Medium'),        # Medium size truck
        ('Heavy', 'Heavy'),          # Heavy duty truck
    )

    # Foreign key relationship to the User model (driver who owns this truck)
    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete truck if driver is deleted
        related_name='trucks',       # Reverse relationship name
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    # Truck basic information
    truck_type = models.CharField(max_length=20, choices=TRUCK_TYPE_CHOICES, blank=True, null=True)  # Type of truck
    registration_no = models.CharField(max_length=50, blank=True, null=True)                         # Registration number

    # Truck size classification
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True, null=True)  # Size category

    # Capacity fields (all in tons, with 2 decimal places)
    total_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)     # Total carrying capacity
    used_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, default=Decimal("0"))  # Currently used capacity
    remaining_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Remaining capacity
    available_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Available for new loads

    # Pricing information
    expected_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Expected rate per ton/km

    # Route and location preferences
    preferred_routes = models.CharField(max_length=200, blank=True, null=True)  # Driver's preferred routes
    pickup_city = models.CharField(max_length=100, blank=True, null=True)        # Preferred pickup city
    drop_city = models.CharField(max_length=100, blank=True, null=True)          # Preferred drop city
    availability_posted = models.BooleanField(default=False)                    # Whether availability is posted

    def __str__(self):
        # String representation of the truck object
        return f"{self.registration_no} - {self.truck_type}"


# ---------------------------
# LOAD MODEL
# ---------------------------
class Load(models.Model):
    # Define the types of loads that can be transported
    LOAD_TYPE_CHOICES = (
        ('Fragile', 'Fragile'),  # Delicate items requiring special handling
        ('Normal', 'Normal'),    # Regular items
    )

    # Define the load transportation modes
    LOAD_MODE_CHOICES = (
        ('Full', 'Full'),        # Full truck load
        ('Partial', 'Partial'), # Partial truck load
    )

    # Define the possible statuses for a load throughout its lifecycle
    STATUS_CHOICES = (
        ('Pre Pending', 'Pre Pending'),  # Load created but not yet visible to drivers
        ('Pending', 'Pending'),          # Load visible to drivers, awaiting acceptance
        ('Accepted', 'Accepted'),        # Load accepted by a driver
        ('Picked', 'Picked'),            # Load picked up by driver
        ('Rejected', 'Rejected'),        # Load rejected by driver
        ('Completed', 'Completed'),      # Load delivered and completed
    )

    # Relationships
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)  # User who created the load
    created_by_role = models.CharField(
        max_length=10,
        choices=(('trader', 'Trader'), ('sme', 'SME')),  # Who created this load
        blank=True,
        null=True,
    )

    # Location information
    pickup_location = models.CharField(max_length=100, blank=True, null=True)  # Pickup city/location name
    drop_location = models.CharField(max_length=100, blank=True, null=True)    # Drop city/location name
    pickup_address = models.TextField(blank=True, null=True)                   # Detailed pickup address
    drop_address = models.TextField(blank=True, null=True)                     # Detailed drop address
    
    # GPS coordinates for precise location tracking (7 decimal places for high precision)
    pickup_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup latitude
    pickup_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup longitude
    drop_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop latitude
    drop_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop longitude
    
    # Route information
    route_distance_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Distance in kilometers
    route_duration_minutes = models.IntegerField(blank=True, null=True)                                  # Estimated duration in minutes
    is_scheduled = models.BooleanField(default=False)  # Whether this is a scheduled load

    # Load specifications and pricing (15 total digits, 2 decimal places for large values)
    weight = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)  # Load weight in tons

    load_type = models.CharField(max_length=10, choices=LOAD_TYPE_CHOICES, blank=True, null=True)  # Type of load (Fragile/Normal)
    load_mode = models.CharField(max_length=10, choices=LOAD_MODE_CHOICES, blank=True, null=True)  # Load mode (Full/Partial)

    # Budget and pricing information
    budget_rate = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)        # Rate per unit (ton/km)
    calculated_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)    # System-calculated budget
    final_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)          # Final negotiated budget

    # Timing information
    pickup_time = models.DateTimeField(blank=True, null=True)  # Scheduled pickup time

    # Load status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True)  # Current load status

    # Assigned driver and truck relationships
    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.SET_NULL,   # Keep load if driver is deleted
        related_name='driver_loads', # Reverse relationship name
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    truck = models.ForeignKey(
        Truck,                       # Reference to Truck model
        on_delete=models.SET_NULL,   # Keep load if truck is deleted
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )
    
    # Bulk booking relationship (used for SME bulk bookings)
    bulk_booking = models.ForeignKey(
        'BulkBooking',               # Reference to BulkBooking model (string to avoid circular import)
        on_delete=models.SET_NULL,   # Keep load if bulk booking is deleted
        related_name='loads',        # Reverse relationship name
        blank=True,                  # Field can be blank
        null=True,                   # Field can be null
    )

    # Driver live tracking information (7 decimal places for GPS precision)
    driver_current_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Driver's current latitude
    driver_current_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True) # Driver's current longitude
    driver_location_updated_at = models.DateTimeField(blank=True, null=True)  # When driver location was last updated

    def __str__(self):
        # String representation showing pickup and drop locations
        return f"{self.pickup_location} → {self.drop_location}"


# ---------------------------
# DRIVER AVAILABILITY
# ---------------------------
class DriverAvailability(models.Model):
    # Driver relationship - which driver is available
    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete availability if driver is deleted
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    # Truck relationship - which truck is available
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, blank=True, null=True)  # Available truck

    # Route information
    route_from = models.CharField(max_length=100, blank=True, null=True)  # Starting location
    route_to = models.CharField(max_length=100, blank=True, null=True)    # Destination location

    # Date and time information
    date = models.DateField(blank=True, null=True)              # Date of availability
    available_time = models.TimeField(blank=True, null=True)     # Specific time available

    # Capacity information (10 total digits, 2 decimal places)
    total_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)     # Total truck capacity
    available_capacity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Available capacity for loads

    # Pricing information
    current_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Current rate per unit

    def __str__(self):
        # String representation showing driver and route
        return f"{self.driver} | {self.route_from} → {self.route_to}"


# ---------------------------
# BOOKING
# ---------------------------
class Booking(models.Model):
    # Define the possible statuses for a booking
    STATUS_CHOICES = (
        ('Pending', 'Pending'),    # Booking offered, awaiting driver response
        ('Accepted', 'Accepted'),  # Booking accepted by driver
        ('Rejected', 'Rejected'),  # Booking rejected by driver
    )

    # Relationships
    load = models.ForeignKey(Load, on_delete=models.CASCADE, blank=True, null=True)  # Associated load
    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.SET_NULL,   # Keep booking if driver is deleted
        related_name='booking_driver', # Reverse relationship name
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    # Driver availability relationship (when booking comes from availability posting)
    driver_availability = models.ForeignKey(
        DriverAvailability,          # Reference to DriverAvailability model
        on_delete=models.CASCADE,    # Delete booking if availability is deleted
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, blank=True, null=True)  # Assigned truck

    # Booking details
    offered_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Price offered by driver
    booked_weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Weight that was booked
    is_partial = models.BooleanField(default=False)  # Whether this is a partial load booking

    # Booking status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True)  # Current booking status

    def __str__(self):
        # String representation of the booking
        return f"Booking {self.id}"

    def _resolve_truck_for_capacity(self):
        """Helper method to find the truck associated with this booking for capacity validation"""
        # First try to get directly assigned truck
        if self.truck_id:
            return self.truck
        # Try to get truck from driver availability
        if self.driver_availability_id and self.driver_availability and self.driver_availability.truck_id:
            return self.driver_availability.truck
        # Try to get any truck associated with the driver
        if self.driver_id:
            return Truck.objects.filter(driver=self.driver).order_by("id").first()
        # No truck found
        return None

    def save(self, *args, **kwargs):
        """Custom save method with capacity validation when accepting bookings"""
        # Use database transaction to ensure atomicity
        with transaction.atomic():
            previous_status = None
            # Get previous status if this is an existing booking
            if self.pk:
                previous_status = (
                    Booking.objects.select_for_update()  # Lock the record for update
                    .filter(pk=self.pk)                 # Filter by primary key
                    .values_list("status", flat=True)   # Get only the status field
                    .first()                            # Get the first (and only) result
                )

            # Check if booking status changed to 'Accepted'
            became_accepted = self.status == "Accepted" and previous_status != "Accepted"
            # If not becoming accepted, proceed with normal save
            if not became_accepted:
                return super().save(*args, **kwargs)

            # Validation for accepting bookings
            if self.booked_weight in (None, ""):
                # Require booked_weight when accepting a booking
                raise ValidationError({"booked_weight": "booked_weight is required when accepting a booking."})

            # Convert booked_weight to Decimal for comparison
            requested_weight = Decimal(str(self.booked_weight))
            if requested_weight <= 0:
                # Ensure booked_weight is positive
                raise ValidationError({"booked_weight": "booked_weight must be greater than zero."})

            # Get the target truck for capacity validation
            target_truck = self._resolve_truck_for_capacity()
            if not target_truck:
                # Raise error if no truck is available for this booking
                raise ValidationError({"truck": "No truck available for this booking."})

            # Lock the truck record for update to prevent race conditions
            locked_truck = Truck.objects.select_for_update().get(pk=target_truck.pk)
            # Get truck capacity (convert to Decimal, default to 0 if None)
            truck_capacity = Decimal(str(locked_truck.total_capacity or 0))
            if truck_capacity <= 0:
                # Raise error if truck capacity is not properly configured
                raise ValidationError({"truck": "Truck capacity is not configured."})

            # Check if requested weight exceeds truck capacity
            if requested_weight > truck_capacity:
                # Raise error if load is too heavy for the truck
                raise ValidationError(
                    {"booked_weight": "Load exceeds your truck capacity."}
                )

            # Assign the locked truck to this booking
            self.truck = locked_truck
            # If no driver is assigned but truck has a driver, assign the truck's driver
            if not self.driver_id and locked_truck.driver_id:
                self.driver = locked_truck.driver

            # Save the booking with all validations passed
            super().save(*args, **kwargs)


# ---------------------------
# BULK BOOKING
# ---------------------------
class BulkBooking(models.Model):
    # SME relationship - which SME created this bulk booking
    sme = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete bulk booking if SME is deleted
        limit_choices_to={'role': 'sme'},  # Only allow users with 'sme' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    # Bulk booking information
    number_of_loads = models.IntegerField(blank=True, null=True)  # Total number of loads in this booking

    # Route and location information
    route = models.CharField(max_length=200, blank=True, null=True)              # Route description
    pickup_location = models.CharField(max_length=100, blank=True, null=True)      # Pickup location name
    drop_location = models.CharField(max_length=100, blank=True, null=True)        # Drop location name
    pickup_address = models.TextField(blank=True, null=True)                       # Detailed pickup address
    drop_address = models.TextField(blank=True, null=True)                         # Detailed drop address
    
    # GPS coordinates for precise location tracking (7 decimal places for high precision)
    pickup_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup latitude
    pickup_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup longitude
    drop_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop latitude
    drop_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop longitude
    
    # Route information
    route_distance_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Distance in kilometers
    route_duration_minutes = models.IntegerField(blank=True, null=True)                                  # Estimated duration in minutes

    # Timestamp information
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)  # When the bulk booking was created

    def __str__(self):
        # String representation of the bulk booking
        return f"Bulk {self.id}"


class BulkBookingItem(models.Model):
    # Define the possible statuses for a bulk booking item
    STATUS_CHOICES = (
        ('Pending', 'Pending'),      # Item is pending assignment
        ('Assigned', 'Assigned'),    # Item has been assigned to driver
        ('Accepted', 'Accepted'),    # Item has been accepted by driver
        ('Rejected', 'Rejected'),    # Item has been rejected by driver
        ('Completed', 'Completed'),  # Item has been completed
    )

    # Relationships
    bulk_booking = models.ForeignKey(
        BulkBooking,                 # Reference to BulkBooking model
        on_delete=models.CASCADE,    # Delete item if bulk booking is deleted
        related_name='items'         # Reverse relationship name
    )
    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.SET_NULL,   # Keep item if driver is deleted
        related_name='bulk_booking_items', # Reverse relationship name
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )
    truck = models.ForeignKey(
        Truck,                       # Reference to Truck model
        on_delete=models.SET_NULL,   # Keep item if truck is deleted
        related_name='bulk_booking_items', # Reverse relationship name
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )
    load = models.ForeignKey(
        Load,                        # Reference to Load model
        on_delete=models.SET_NULL,   # Keep item if load is deleted
        related_name='bulk_booking_items', # Reverse relationship name
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )
    
    # Item details and pricing (15 total digits, 2 decimal places for large values)
    weight = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)        # Item weight in tons
    calculated_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)  # System-calculated budget
    final_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)        # Final negotiated budget
    
    # Item status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')  # Current item status

    def __str__(self):
        # String representation showing item ID and parent bulk booking ID
        return f"BulkBookingItem {self.id} (Bulk {self.bulk_booking_id})"


class LoadStatusHistory(models.Model):
    # Load relationship - which load this status change is for
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='status_history')  # Associated load
    # Status at this point in time (uses same choices as Load model)
    status = models.CharField(max_length=20, choices=Load.STATUS_CHOICES, blank=True, null=True)  # Load status
    # When this status change occurred
    timestamp = models.DateTimeField(auto_now_add=True)  # Automatic timestamp
    # Where this status change occurred (optional)
    location = models.TextField(blank=True, null=True)   # Location description

    def __str__(self):
        # String representation showing load ID, status, and timestamp
        return f"Load {self.load_id} -> {self.status} @ {self.timestamp}"


class RepeatOrder(models.Model):
    # SME relationship - which SME created this repeat order
    user = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete repeat order if SME is deleted
        related_name='repeat_orders', # Reverse relationship name
        limit_choices_to={'role': 'sme'}  # Only allow users with 'sme' role
    )
    # Reference to the original load that is being repeated
    previous_load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='repeat_orders')  # Original load
    # When this repeat order was created
    created_at = models.DateTimeField(auto_now_add=True)  # Automatic timestamp

    def __str__(self):
        # String representation showing repeat order ID, user ID, and original load ID
        return f"RepeatOrder {self.id} (User {self.user_id}, Load {self.previous_load_id})"


# ---------------------------
# SCHEDULED PICKUP
# ---------------------------
class ScheduledPickup(models.Model):
    # SME relationship - which SME created this scheduled pickup
    sme = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete scheduled pickup if SME is deleted
        limit_choices_to={'role': 'sme'},  # Only allow users with 'sme' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    # Scheduled timing information
    pickup_date = models.DateField(blank=True, null=True)      # Scheduled pickup date
    pickup_time = models.TimeField(blank=True, null=True)     # Scheduled pickup time

    # Load specifications (15 total digits, 2 decimal places for large values)
    weight = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)  # Load weight in tons

    # Load characteristics
    load_type = models.CharField(max_length=10, blank=True, null=True)  # Type of load (Fragile/Normal)
    load_mode = models.CharField(max_length=10, blank=True, null=True)  # Load mode (Full/Partial)

    # Route and location information
    route = models.CharField(max_length=200, blank=True, null=True)              # Route description
    pickup_location = models.CharField(max_length=100, blank=True, null=True)      # Pickup location name
    drop_location = models.CharField(max_length=100, blank=True, null=True)        # Drop location name
    pickup_address = models.TextField(blank=True, null=True)                       # Detailed pickup address
    drop_address = models.TextField(blank=True, null=True)                         # Detailed drop address
    
    # GPS coordinates for precise location tracking (7 decimal places for high precision)
    pickup_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup latitude
    pickup_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)  # Pickup longitude
    drop_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop latitude
    drop_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)      # Drop longitude
    
    # Route information
    route_distance_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Distance in kilometers
    route_duration_minutes = models.IntegerField(blank=True, null=True)                                  # Estimated duration in minutes
    
    # Budget information (15 total digits, 2 decimal places for large values)
    calculated_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)  # System-calculated budget
    final_budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)        # Final negotiated budget
    
    # Conversion status
    is_converted = models.BooleanField(default=False)  # Whether this scheduled pickup has been converted to a load
    
    # Reference to the converted load (when is_converted is True)
    converted_load = models.ForeignKey(
        Load,                        # Reference to Load model
        on_delete=models.SET_NULL,   # Keep scheduled pickup if load is deleted
        blank=True,                  # Field can be blank
        null=True,                   # Field can be null
        related_name='scheduled_pickups', # Reverse relationship name
    )

    def __str__(self):
        # String representation of the scheduled pickup
        return f"Scheduled {self.id}"


# ---------------------------
# INVOICE
# ---------------------------
class Invoice(models.Model):
    # Define the available payment methods
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),        # Cash payment
        ('online', 'Online'),    # Online payment
        ('wallet', 'Wallet'),    # Wallet payment
    )
    # Define the possible payment statuses
    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'Unpaid'),    # Invoice is not paid
        ('paid', 'Paid'),        # Invoice has been paid
    )

    # Relationships
    load = models.ForeignKey(Load, on_delete=models.CASCADE, blank=True, null=True)  # Associated load

    sme = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete invoice if SME is deleted
        limit_choices_to={'role': 'sme'},  # Only allow users with 'sme' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    driver = models.ForeignKey(
        User,                        # Reference to User model
        on_delete=models.CASCADE,    # Delete invoice if driver is deleted
        related_name='driver_invoice', # Reverse relationship name
        limit_choices_to={'role': 'driver'},  # Only allow users with 'driver' role
        blank=True,                  # Field can be blank
        null=True                    # Field can be null
    )

    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, blank=True, null=True)  # Associated booking

    # Invoice details
    route = models.CharField(max_length=200, blank=True, null=True)              # Route description
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Total invoice cost
    paid = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Amount paid
    
    # Payment information
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, blank=True, null=True)  # Current payment status
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)  # Payment method used
    transaction_id = models.CharField(max_length=100, blank=True, null=True)  # Transaction ID for tracking
    
    # Date information
    date = models.DateField(blank=True, null=True)  # Invoice date

    def __str__(self):
        # String representation of the invoice
        return f"Invoice {self.id}"
