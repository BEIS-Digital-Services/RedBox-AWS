# Generated by Django 5.1.2 on 2024-11-01 14:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('redbox_core', '0059_alter_aisettings_retrieval_system_prompt'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='invite_accepted_at',
        ),
        migrations.RemoveField(
            model_name='user',
            name='invited_at',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_token_sent_at',
        ),
        migrations.RemoveField(
            model_name='user',
            name='verified',
        ),
    ]
