from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loadify_api', '0009_load_improvements_and_booking_signals_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduledpickup',
            name='converted_load',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scheduled_pickups', to='loadify_api.load'),
        ),
        migrations.AddField(
            model_name='scheduledpickup',
            name='is_converted',
            field=models.BooleanField(default=False),
        ),
    ]
