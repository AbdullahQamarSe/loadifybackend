from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loadify_api', '0008_truck_availability_posted'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='driver',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'role': 'driver'},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='booking_driver',
                to='loadify_api.user',
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='is_partial',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='load',
            name='created_by_role',
            field=models.CharField(
                blank=True,
                choices=[('trader', 'Trader'), ('sme', 'SME')],
                max_length=10,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='BulkBookingItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Rejected', 'Rejected'), ('Completed', 'Completed')], default='Pending', max_length=20)),
                ('bulk_booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='loadify_api.bulkbooking')),
            ],
        ),
        migrations.CreateModel(
            name='LoadStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(blank=True, choices=[('Pre Pending', 'Pre Pending'), ('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Picked', 'Picked'), ('Rejected', 'Rejected'), ('Completed', 'Completed')], max_length=20, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('location', models.TextField(blank=True, null=True)),
                ('load', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_history', to='loadify_api.load')),
            ],
        ),
        migrations.CreateModel(
            name='RepeatOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('previous_load', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='repeat_orders', to='loadify_api.load')),
                ('user', models.ForeignKey(limit_choices_to={'role': 'sme'}, on_delete=django.db.models.deletion.CASCADE, related_name='repeat_orders', to='loadify_api.user')),
            ],
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='booking_id',
        ),
        migrations.AddField(
            model_name='invoice',
            name='booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='loadify_api.booking'),
        ),
    ]
