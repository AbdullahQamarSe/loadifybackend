from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loadify_api", "0006_load_driver_live_location_and_picked_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="load",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Pre Pending", "Pre Pending"),
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
