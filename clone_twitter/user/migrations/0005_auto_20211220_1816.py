# Generated by Django 3.2.6 on 2021-12-20 18:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_auto_20211219_0440'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='header_img',
            field=models.ImageField(blank=True, null=True, upload_to=''),
        ),
        migrations.AlterField(
            model_name='user',
            name='profile_img',
            field=models.ImageField(blank=True, null=True, upload_to=''),
        ),
    ]