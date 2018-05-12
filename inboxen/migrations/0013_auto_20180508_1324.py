# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-05-08 13:24
from __future__ import unicode_literals

from django.db import migrations


def rebuild_watson(apps, schema_editor):
    # migration made into a no-op because the buildwatson command won't be able
    # to see new fields. buildwatson can be called manually after migrating if
    # needed
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inboxen', '0013_remove_userprofile_pool_amount'),
        ('watson', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(rebuild_watson, rebuild_watson),
    ]
