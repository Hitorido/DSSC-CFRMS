from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_merge_0002_user_is_synthetic_0002_user_profile_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('ADMIN', 'Admin'),
                    ('STAFF', 'Staff'),
                    ('FACULTY', 'Faculty'),
                    ('REQUESTER', 'Student Requester'),
                ],
                default='REQUESTER',
                help_text='System authorization level determining access and permissions.',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='user_type',
            field=models.CharField(
                blank=True,
                choices=[('STUDENT', 'Student'), ('FACULTY', 'Faculty')],
                default='',
                help_text='Legacy requester classification. Account permissions are controlled by role.',
                max_length=20,
            ),
        ),
    ]
