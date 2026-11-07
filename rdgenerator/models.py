from django.db import models

class GithubRun(models.Model):
    # AutoField (not IntegerField) so the primary key is database-generated on
    # every backend. IntegerField has no auto-increment outside SQLite, where it
    # only works by accident via the rowid alias.
    id = models.AutoField(verbose_name="ID", primary_key=True)
    # unique=True: lookups use .first(), which is non-deterministic when the
    # same uuid appears more than once. Indexed for the polling endpoint.
    uuid = models.CharField(verbose_name="uuid", max_length=100, unique=True)
    status = models.CharField(verbose_name="status", max_length=100)
