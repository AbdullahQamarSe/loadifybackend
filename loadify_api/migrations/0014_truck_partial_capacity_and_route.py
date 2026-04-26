from decimal import Decimal

from django.db import migrations, models


def backfill_truck_capacity_fields(apps, schema_editor):
    Truck = apps.get_model("loadify_api", "Truck")
    for truck in Truck.objects.all():
        total = truck.total_capacity if truck.total_capacity is not None else Decimal("0")
        existing_remaining = truck.available_capacity if truck.available_capacity is not None else total
        if existing_remaining < 0:
            existing_remaining = Decimal("0")
        if total < 0:
            total = Decimal("0")
        if existing_remaining > total:
            existing_remaining = total
        truck.remaining_capacity = existing_remaining
        truck.used_capacity = total - existing_remaining
        if truck.used_capacity < 0:
            truck.used_capacity = Decimal("0")
        truck.save(update_fields=["remaining_capacity", "used_capacity"])


class Migration(migrations.Migration):

    dependencies = [
        ("loadify_api", "0013_scheduled_bulk_invoice_upgrades"),
    ]

    operations = [
        migrations.AddField(
            model_name="truck",
            name="drop_city",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="truck",
            name="pickup_city",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="truck",
            name="remaining_capacity",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="truck",
            name="used_capacity",
            field=models.DecimalField(blank=True, decimal_places=2, default=Decimal("0"), max_digits=10, null=True),
        ),
        migrations.RunPython(backfill_truck_capacity_fields, migrations.RunPython.noop),
    ]
