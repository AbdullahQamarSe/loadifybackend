from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loadify_api", "0007_load_pre_pending_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="truck",
            name="availability_posted",
            field=models.BooleanField(default=False),
        ),
    ]
