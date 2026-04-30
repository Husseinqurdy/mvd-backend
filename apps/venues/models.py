from django.db import models


class Building(models.Model):
    name     = models.CharField(max_length=150, unique=True)
    code     = models.CharField(max_length=30, unique=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'buildings'
        ordering = ['name']

    def __str__(self):
        return self.name


class Venue(models.Model):
    class VenueType(models.TextChoices):
        LECTURE_HALL = 'LECTURE_HALL', 'Lecture Hall'
        LAB          = 'LAB',          'Laboratory'
        SEMINAR_ROOM = 'SEMINAR_ROOM', 'Seminar Room'
        THEATRE      = 'THEATRE',      'Theatre'
        LIBRARY      = 'LIBRARY',      'Library Room'
        OTHER        = 'OTHER',        'Other'

    building   = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='venues')
    name       = models.CharField(max_length=150)
    code       = models.CharField(max_length=30, unique=True)
    venue_type = models.CharField(max_length=20, choices=VenueType.choices, default=VenueType.LECTURE_HALL)
    capacity   = models.PositiveIntegerField(default=0)
    wing       = models.CharField(max_length=150, blank=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        db_table = 'venues'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'
