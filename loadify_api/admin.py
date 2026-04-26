from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
    User, Truck, Load, DriverAvailability, Booking,
    BulkBooking, BulkBookingItem, LoadStatusHistory,
    RepeatOrder, ScheduledPickup, Invoice
)


# ---------------------------
# INLINES
# ---------------------------
class LoadStatusHistoryInline(admin.TabularInline):
    model = LoadStatusHistory
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('status', 'location', 'timestamp')


class BulkBookingItemInline(admin.TabularInline):
    model = BulkBookingItem
    extra = 0
    fields = ('driver', 'truck', 'weight', 'status')
    readonly_fields = ('load',)


# ---------------------------
# USER ADMIN
# ---------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'phone_number', 'city', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 'city')
        }),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('Trader Details'), {
            'fields': ('goods_type',),
            'classes': ('collapse',),
        }),
        (_('Driver Details'), {
            'fields': ('cnic',),
            'classes': ('collapse',),
        }),
        (_('SME Details'), {
            'fields': ('business_name', 'business_type', 'ntn', 'owner_name', 'business_email', 'business_address'),
            'classes': ('collapse',),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """Customize fieldsets based on user role."""
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.role:
            # Show only relevant role-specific fields
            if obj.role == 'trader':
                fieldsets = self._filter_fieldsets(fieldsets, ['Trader Details'])
            elif obj.role == 'driver':
                fieldsets = self._filter_fieldsets(fieldsets, ['Driver Details'])
            elif obj.role == 'sme':
                fieldsets = self._filter_fieldsets(fieldsets, ['SME Details'])
        return fieldsets

    def _filter_fieldsets(self, fieldsets, keep_sections):
        """Helper to keep only specified sections."""
        return [fs for fs in fieldsets if fs[0] is None or fs[0] in keep_sections]


# ---------------------------
# TRUCK ADMIN
# ---------------------------
@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = (
        'registration_no', 'truck_type', 'size', 'driver',
        'total_capacity', 'available_capacity', 'expected_rate',
        'preferred_routes', 'availability_posted'
    )
    list_filter = ('truck_type', 'size', 'availability_posted')
    search_fields = ('registration_no', 'driver__username', 'preferred_routes')
    raw_id_fields = ('driver',)
    readonly_fields = ('available_capacity',)  # Capacity managed via Booking logic


# ---------------------------
# LOAD ADMIN
# ---------------------------
@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'created_by_role', 'pickup_location', 'drop_location',
        'weight', 'load_type', 'load_mode', 'status', 'driver', 'truck',
        'pickup_time', 'is_scheduled'
    )
    list_filter = (
        'status', 'load_type', 'load_mode', 'is_scheduled', 'created_by_role',
        'pickup_time'
    )
    search_fields = (
        'pickup_location', 'drop_location', 'pickup_address', 'drop_address',
        'user__username', 'driver__username', 'truck__registration_no'
    )
    raw_id_fields = ('user', 'driver', 'truck', 'bulk_booking')
    readonly_fields = (
        'route_distance_km', 'route_duration_minutes',
        'driver_current_latitude', 'driver_current_longitude',
        'driver_location_updated_at'
    )
    inlines = [LoadStatusHistoryInline]

    fieldsets = (
        (_('Basic Info'), {
            'fields': ('user', 'created_by_role', 'status', 'pickup_time', 'is_scheduled')
        }),
        (_('Route'), {
            'fields': (
                'pickup_location', 'drop_location', 'pickup_address', 'drop_address',
                'pickup_lat', 'pickup_lng', 'drop_lat', 'drop_lng',
                'route_distance_km', 'route_duration_minutes'
            )
        }),
        (_('Load Details'), {
            'fields': ('weight', 'load_type', 'load_mode', 'budget_rate')
        }),
        (_('Assignment'), {
            'fields': ('driver', 'truck', 'bulk_booking')
        }),
        (_('Driver Tracking'), {
            'fields': (
                'driver_current_latitude', 'driver_current_longitude',
                'driver_location_updated_at'
            ),
            'classes': ('collapse',)
        }),
    )


# ---------------------------
# DRIVER AVAILABILITY ADMIN
# ---------------------------
@admin.register(DriverAvailability)
class DriverAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'driver', 'truck', 'route_from', 'route_to', 'date',
        'total_capacity', 'available_capacity', 'current_rate', 'available_time'
    )
    list_filter = ('date', 'route_from', 'route_to')
    search_fields = ('driver__username', 'truck__registration_no', 'route_from', 'route_to')
    raw_id_fields = ('driver', 'truck')
    readonly_fields = ('available_capacity',)  # Managed via Booking logic


# ---------------------------
# BOOKING ADMIN
# ---------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'load', 'driver', 'truck', 'offered_price',
        'booked_weight', 'is_partial', 'status'
    )
    list_filter = ('status', 'is_partial')
    search_fields = ('load__pickup_location', 'load__drop_location', 'driver__username')
    raw_id_fields = ('load', 'driver', 'driver_availability', 'truck')
    readonly_fields = ('is_partial',)  # Auto-calculated on save

    fieldsets = (
        (None, {
            'fields': ('load', 'driver', 'driver_availability', 'truck')
        }),
        (_('Booking Details'), {
            'fields': ('offered_price', 'booked_weight', 'is_partial', 'status')
        }),
    )

    def save_model(self, request, obj, form, change):
        """Ensure capacity updates are handled via model's save logic."""
        super().save_model(request, obj, form, change)


# ---------------------------
# BULK BOOKING ADMIN
# ---------------------------
@admin.register(BulkBooking)
class BulkBookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sme', 'number_of_loads', 'route',
        'pickup_location', 'drop_location', 'created_at'
    )
    list_filter = ('created_at', 'pickup_location', 'drop_location')
    search_fields = ('sme__username', 'route', 'pickup_location', 'drop_location')
    raw_id_fields = ('sme',)
    readonly_fields = ('created_at', 'route_distance_km', 'route_duration_minutes')
    inlines = [BulkBookingItemInline]

    fieldsets = (
        (None, {
            'fields': ('sme', 'number_of_loads', 'route')
        }),
        (_('Locations'), {
            'fields': (
                'pickup_location', 'drop_location', 'pickup_address', 'drop_address',
                'pickup_lat', 'pickup_lng', 'drop_lat', 'drop_lng',
                'route_distance_km', 'route_duration_minutes'
            )
        }),
    )


# ---------------------------
# BULK BOOKING ITEM ADMIN
# ---------------------------
@admin.register(BulkBookingItem)
class BulkBookingItemAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'bulk_booking', 'driver', 'truck', 'weight', 'status'
    )
    list_filter = ('status',)
    search_fields = ('bulk_booking__id', 'driver__username', 'truck__registration_no')
    raw_id_fields = ('bulk_booking', 'driver', 'truck', 'load')
    readonly_fields = ('load',)  # Load may be created later


# ---------------------------
# LOAD STATUS HISTORY ADMIN
# ---------------------------
@admin.register(LoadStatusHistory)
class LoadStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'load', 'status', 'timestamp', 'location')
    list_filter = ('status', 'timestamp')
    search_fields = ('load__id', 'location')
    raw_id_fields = ('load',)
    readonly_fields = ('timestamp',)


# ---------------------------
# REPEAT ORDER ADMIN
# ---------------------------
@admin.register(RepeatOrder)
class RepeatOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'previous_load', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'previous_load__id')
    raw_id_fields = ('user', 'previous_load')
    readonly_fields = ('created_at',)


# ---------------------------
# SCHEDULED PICKUP ADMIN
# ---------------------------
@admin.register(ScheduledPickup)
class ScheduledPickupAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sme', 'pickup_date', 'pickup_time', 'weight',
        'load_type', 'load_mode', 'route', 'is_converted'
    )
    list_filter = ('is_converted', 'pickup_date', 'load_type', 'load_mode')
    search_fields = ('sme__username', 'route', 'pickup_location', 'drop_location')
    raw_id_fields = ('sme', 'converted_load')
    readonly_fields = ('route_distance_km', 'route_duration_minutes')

    fieldsets = (
        (None, {
            'fields': ('sme', 'pickup_date', 'pickup_time', 'is_converted', 'converted_load')
        }),
        (_('Load Details'), {
            'fields': ('weight', 'load_type', 'load_mode')
        }),
        (_('Route'), {
            'fields': (
                'route', 'pickup_location', 'drop_location',
                'pickup_address', 'drop_address',
                'pickup_lat', 'pickup_lng', 'drop_lat', 'drop_lng',
                'route_distance_km', 'route_duration_minutes'
            )
        }),
    )


# ---------------------------
# INVOICE ADMIN
# ---------------------------
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'load', 'sme', 'driver', 'route', 'cost',
        'payment_status', 'payment_method', 'date', 'transaction_id'
    )
    list_filter = ('payment_status', 'payment_method', 'date')
    search_fields = (
        'load__id', 'sme__username', 'driver__username',
        'route', 'transaction_id'
    )
    raw_id_fields = ('load', 'sme', 'driver', 'booking')
    readonly_fields = ('date',)

    fieldsets = (
        (None, {
            'fields': ('load', 'sme', 'driver', 'booking', 'route', 'cost')
        }),
        (_('Payment Details'), {
            'fields': ('payment_status', 'payment_method', 'transaction_id', 'date')
        }),
    )