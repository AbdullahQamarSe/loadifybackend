from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loadify_api", "0014_truck_partial_capacity_and_route"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulkbookingitem",
            name="calculated_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="bulkbookingitem",
            name="final_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="load",
            name="calculated_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="load",
            name="final_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="scheduledpickup",
            name="calculated_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="scheduledpickup",
            name="final_budget",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
