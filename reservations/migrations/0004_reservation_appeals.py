import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('reservations', '0003_completion_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='appeal_count',
            field=models.PositiveSmallIntegerField(
                default=0,
                editable=False,
                validators=[django.core.validators.MaxValueValidator(3)],
                help_text='Number of appeals submitted for this reservation (maximum three).',
            ),
        ),
        migrations.AddConstraint(
            model_name='reservation',
            constraint=models.CheckConstraint(
                condition=models.Q(appeal_count__gte=0, appeal_count__lte=3),
                name='reservation_appeal_limit',
            ),
        ),
        migrations.CreateModel(
            name='ReservationAppeal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempt', models.PositiveSmallIntegerField(validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(3),
                ])),
                ('reason', models.TextField(max_length=2000)),
                ('previous_decline_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reservation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='appeals',
                    to='reservations.reservation',
                )),
            ],
            options={
                'ordering': ['-attempt'],
                'constraints': [
                    models.UniqueConstraint(fields=('reservation', 'attempt'), name='appeal_unique_attempt'),
                    models.CheckConstraint(
                        condition=models.Q(attempt__gte=1, attempt__lte=3),
                        name='appeal_attempt_range',
                    ),
                ],
            },
        ),
    ]
