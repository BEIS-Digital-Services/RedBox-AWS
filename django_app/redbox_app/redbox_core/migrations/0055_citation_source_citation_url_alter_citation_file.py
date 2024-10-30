# Generated by Django 5.1.2 on 2024-10-22 12:26

import django.db.models.deletion
from django.db import migrations, models


def back_populate_citations(apps, schema_editor):
    Citation = apps.get_model("redbox_core", "Citation")
    for citation in Citation.objects.all():
        citation.source = "USER UPLOADED DOCUMENT"
        citation.save()


class Migration(migrations.Migration):

    dependencies = [
        ('redbox_core', '0054_activityevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='citation',
            name='source',
            field=models.CharField(blank=True, choices=[('Wikipedia', 'wikipedia'), ('USER UPLOADED DOCUMENT', 'user uploaded document'), ('GOV.UK', 'gov.uk')], help_text='source of citation', max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='citation',
            name='url',
            field=models.URLField(blank=True, help_text='url for external', null=True),
        ),
        migrations.AlterField(
            model_name='citation',
            name='file',
            field=models.ForeignKey(blank=True, help_text='file for internal citation', null=True, on_delete=django.db.models.deletion.CASCADE, to='redbox_core.file'),
        ),
        migrations.RunPython(back_populate_citations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='citation',
            name='source',
            field=models.CharField(choices=[('Wikipedia', 'wikipedia'), ('USER UPLOADED DOCUMENT', 'user uploaded document'), ('GOV.UK', 'gov.uk')], default='USER UPLOADED DOCUMENT', help_text='source of citation', max_length=32),
        ),
    ]