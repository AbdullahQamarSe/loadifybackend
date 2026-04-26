from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loadify_api', '0010_scheduledpickup_conversion_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulkbookingitem',
            name='driver',
            field=models.ForeignKey(blank=True, limit_choices_to={'role': 'driver'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bulk_booking_items', to='loadify_api.user'),
        ),
        migrations.AddField(
            model_name='bulkbookingitem',
            name='load',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bulk_booking_items', to='loadify_api.load'),
        ),
        migrations.AddField(
            model_name='bulkbookingitem',
            name='truck',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bulk_booking_items', to='loadify_api.truck'),
        ),
        migrations.AlterField(
            model_name='bulkbookingitem',
            name='status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Assigned', 'Assigned'), ('Accepted', 'Accepted'), ('Rejected', 'Rejected'), ('Completed', 'Completed')], default='Pending', max_length=20),
        ),
    ]
