from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loadify_api', '0011_bulkbookingitem_assignment_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkbooking',
            name='drop_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='drop_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='drop_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='drop_location',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='pickup_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='pickup_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='pickup_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='pickup_location',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='route_distance_km',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='bulkbooking',
            name='route_duration_minutes',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='drop_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='drop_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='drop_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='pickup_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='pickup_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='pickup_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='route_distance_km',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='route_duration_minutes',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='drop_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='drop_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='drop_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='drop_location',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='pickup_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='pickup_lat',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='pickup_lng',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='pickup_location',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='route_distance_km',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='route_duration_minutes',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
