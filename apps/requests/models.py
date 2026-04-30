from django.db import models
from apps.venues.models import Venue
from apps.accounts.models import User


class VenueRequest(models.Model):
    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    venue        = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='venue_requests')
    reviewed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    purpose      = models.CharField(max_length=300)
    date         = models.DateField()
    start_time   = models.TimeField()
    end_time     = models.TimeField()
    attendees    = models.PositiveIntegerField(default=1)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note   = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'venue_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.requested_by.full_name} → {self.venue.code} on {self.date} [{self.status}]'
