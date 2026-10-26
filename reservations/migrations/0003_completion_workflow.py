import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_faculty_reviewer_role'),
        ('reservations', '0002_reservation_is_synthetic'),
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
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                help_text='Current reservation lifecycle status.',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Staff, faculty, or Admin who approved or declined this reservation.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_reservations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='reviewed_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when the reservation was approved or declined.',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='rejection_reason',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Explanation provided by a reviewer when the request is declined.',
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='completed_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Staff, faculty, or Admin who marked this reservation completed.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='completed_reservations',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='reservation',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
