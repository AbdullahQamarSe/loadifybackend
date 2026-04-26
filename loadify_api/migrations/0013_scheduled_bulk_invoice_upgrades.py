from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loadify_api', '0012_route_and_location_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='payment_method',
            field=models.CharField(blank=True, choices=[('cash', 'Cash'), ('online', 'Online'), ('wallet', 'Wallet')], max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_status',
            field=models.CharField(blank=True, choices=[('unpaid', 'Unpaid'), ('paid', 'Paid')], default='unpaid', max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='load',
            name='bulk_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='loads', to='loadify_api.bulkbooking'),
        ),
        migrations.AddField(
            model_name='load',
            name='is_scheduled',
            field=models.BooleanField(default=False),
        ),
    ]
