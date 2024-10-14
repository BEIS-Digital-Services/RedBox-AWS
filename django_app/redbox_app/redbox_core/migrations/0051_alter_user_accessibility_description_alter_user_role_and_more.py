# Generated by Django 5.1.1 on 2024-10-13 19:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('redbox_core', '0050_aisettings_match_description_boost_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='accessibility_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_1_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_1_duration',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_1_regularity',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_2_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_2_duration',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_2_regularity',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_3_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_3_duration',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='task_3_regularity',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveField(
            model_name='file',
            name='core_file_uuid',
        ),
    ]
