# Generated by Django 3.2.6 on 2022-01-22 18:24

from django.db import migrations, models
import user.models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0014_alter_profilemedia_media'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profilemedia',
            name='media',
            field=models.ImageField(upload_to=user.models.header_media_path),
        ),
        migrations.AlterField(
            model_name='user',
            name='header_img',
            field=models.ImageField(blank=True, null=True, upload_to=user.models.profile_media_path),
        ),
    ]