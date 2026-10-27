# Generated migration for adding facility enhancement fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facilities', '0003_facility_is_synthetic_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='facility',
            name='equipment_list',
            field=models.TextField(blank=True, default='', help_text='Comma-separated list of equipment (e.g., "Projector, Whiteboard, A/C")'),
        ),
        migrations.AddField(
            model_name='facility',
            name='hours_of_operation',
            field=models.CharField(blank=True, default='8am-6pm', help_text='Operating hours (e.g., "8am-6pm weekdays, 9am-5pm weekends")', max_length=200),
        ),
        migrations.AddField(
            model_name='facility',
            name='noise_level',
            field=models.CharField(blank=True, choices=[('silent', 'Silent'), ('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='low', help_text='Noise level classification for amenity filtering', max_length=20),
        ),
        migrations.AddField(
            model_name='facility',
            name='floor_number',
            field=models.IntegerField(blank=True, help_text='Building floor number (e.g., 2 for 2nd floor)', null=True),
        ),
        migrations.AddField(
            model_name='facility',
            name='building_code',
            field=models.CharField(blank=True, default='', help_text='Building identifier (e.g., "ADMIN", "SCI")', max_length=10),
        ),
        migrations.AddField(
            model_name='facility',
            name='has_wheelchair_access',
            field=models.BooleanField(default=True, help_text='Indicates wheelchair accessibility'),
        ),
        migrations.AddIndex(
            model_name='facility',
            index=models.Index(fields=['noise_level', 'capacity'], name='fac_noise_capacity_idx'),
        ),
        migrations.AddIndex(
            model_name='facility',
            index=models.Index(fields=['building_code', 'floor_number'], name='fac_building_floor_idx'),
        ),
    ]
