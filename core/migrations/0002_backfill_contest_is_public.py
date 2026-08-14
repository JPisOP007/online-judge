from django.db import migrations


def relist_existing_contests(apps, schema_editor):
    """Undo the is_public values the create/edit form never asked for.

    Contest.is_public defaults to True, but the field was in ContestForm's
    Meta.fields while appearing on neither template. An unchecked checkbox is
    an absent POST key, which a form BooleanField reads as False, so every
    contest saved through the UI was written back as unlisted - and nothing
    read the flag, so nobody noticed until the contest list started honouring
    it and the contests disappeared for everyone but their author and the
    admins.

    Before the form was fixed there was no way to unlist a contest through the
    site at all, so every False in the data is that bug rather than a choice,
    and they all go back to listed. Deliberately unlisted contests can now be
    created, and this migration runs once, before any of them exist.
    """
    Contest = apps.get_model('core', 'Contest')
    Contest.objects.filter(is_public=False).update(is_public=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # Not reversible on purpose: the old values carried no information, so
        # there is nothing to restore them to.
        migrations.RunPython(relist_existing_contests, migrations.RunPython.noop),
    ]
