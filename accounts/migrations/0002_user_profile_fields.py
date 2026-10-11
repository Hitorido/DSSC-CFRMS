from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='bio',
            field=models.CharField(blank=True, default='', help_text='A short profile description (280 characters maximum).', max_length=280),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, default='', help_text='Optional contact number.', max_length=30),
        ),
        migrations.AddField(
            model_name='user',
            name='profile_image',
            field=models.ImageField(blank=True, help_text='Optional profile photo. Maximum file size: 5 MB.', upload_to='profile_images/'),
        ),
    ]
