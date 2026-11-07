"""Switch GithubRun.id to a database-generated AutoField and make uuid unique.

IntegerField primary keys are only auto-assigned on SQLite, where the column
happens to be a rowid alias. On MySQL/PostgreSQL the same DDL has no
auto-increment, so every save() raises IntegrityError.

uuid becomes unique because views look rows up with .first(), which returns an
arbitrary row when duplicates exist. Existing duplicates (including the garbage
rows written by the old unauthenticated /creategh route) are pruned first,
keeping the highest id per uuid, so the constraint can be applied safely.
"""

from django.db import migrations, models


def dedupe_uuids(apps, schema_editor):
    GithubRun = apps.get_model('rdgenerator', 'GithubRun')
    seen = set()
    stale_ids = []
    # Highest id first: that row is the most recent state for its uuid.
    for run in GithubRun.objects.order_by('-id').values_list('id', 'uuid'):
        run_id, run_uuid = run
        if run_uuid in seen:
            stale_ids.append(run_id)
        else:
            seen.add(run_uuid)
    if stale_ids:
        GithubRun.objects.filter(id__in=stale_ids).delete()


def noop_reverse(apps, schema_editor):
    # Restoring removed duplicates is neither possible nor desirable.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rdgenerator', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(dedupe_uuids, noop_reverse),
        migrations.AlterField(
            model_name='githubrun',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='githubrun',
            name='uuid',
            field=models.CharField(max_length=100, unique=True, verbose_name='uuid'),
        ),
    ]
