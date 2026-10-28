# Generated migration for APPEAL status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0005_add_performance_indexes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reservation',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('APPROVED', 'Approved'),
                    ('COMPLETED', 'Completed'),
                    ('REJECTED', 'Declined'),
                    ('APPEAL', 'Appeal'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
