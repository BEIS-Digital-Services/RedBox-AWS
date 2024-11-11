# Generated by Django 5.1.2 on 2024-11-05 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('redbox_core', '0063_alter_activityevent_message'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aisettings',
            name='retrieval_system_prompt',
            field=models.TextField(default='You are a specialized GPT-4o agent. Your task is to answer user queries with reliable sources.\n**You must provide the citations where you use the information to answer.**\nUse UK English spelling in response.\nUse the document `creator_type` as `source_type` if available.\n\n{format_arg}'),
        ),
    ]