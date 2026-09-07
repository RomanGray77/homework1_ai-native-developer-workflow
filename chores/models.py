from django.db import models


class FamilyMember(models.Model):
    name = models.CharField(max_length=150, unique=True, blank=False)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.name
