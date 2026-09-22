from django.db import models


class UnmanagedBaseModel(models.Model):
    """
    Abstract base class that sets managed = False.
    Any model inheriting from this will not be managed by Django's migrations.
    """

    class Meta:
        abstract = True
        managed = False
