from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loadify_api", "0005_remove_truck_cnid_booking_offered_price_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="load",
            name="driver_current_latitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="load",
            name="driver_current_longitude",
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="load",
            name="driver_location_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="load",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Pending", "Pending"),
                    ("Accepted", "Accepted"),
                    ("Picked", "Picked"),
                    ("Rejected", "Rejected"),
                    ("Completed", "Completed"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
