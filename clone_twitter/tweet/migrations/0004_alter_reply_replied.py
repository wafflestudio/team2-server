# Generated by Django 3.2.6 on 2021-12-28 09:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tweet', '0003_alter_tweet_content'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reply',
            name='replied',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replied_by', to='tweet.tweet'),
        ),
    ]
