from django.db import models
from apps.venues.models import Venue
from apps.accounts.models import User


class AcademicPeriod(models.Model):
    name       = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date   = models.DateField()
    is_active  = models.BooleanField(default=False)

    class Meta:
        db_table = 'academic_periods'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            AcademicPeriod.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class College(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'colleges'
        ordering = ['name']

    def __str__(self):
        return self.name


class Department(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='departments')
    name    = models.CharField(max_length=200)
    code    = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'departments'

    def __str__(self):
        return self.name


class Program(models.Model):
    class Level(models.TextChoices):
        DIPLOMA  = 'DIPLOMA', 'Diploma'
        BACHELOR = 'BSC',     'Bachelor'
        MASTERS  = 'MSC',     'Masters'

    department     = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programs')
    name           = models.CharField(max_length=200)
    code           = models.CharField(max_length=50, unique=True)
    level          = models.CharField(max_length=10, choices=Level.choices, default=Level.BACHELOR)
    uqf_level      = models.PositiveSmallIntegerField(default=8)
    duration_years = models.PositiveSmallIntegerField(default=3)

    class Meta:
        db_table = 'programs'
        ordering = ['name']

    def __str__(self):
        return self.name


class TimetableSession(models.Model):
    class Day(models.IntegerChoices):
        MONDAY    = 1, 'Monday'
        TUESDAY   = 2, 'Tuesday'
        WEDNESDAY = 3, 'Wednesday'
        THURSDAY  = 4, 'Thursday'
        FRIDAY    = 5, 'Friday'
        SATURDAY  = 6, 'Saturday'

    period        = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='sessions')
    program       = models.ForeignKey(Program, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    year_of_study = models.PositiveSmallIntegerField(default=1)
    course_code   = models.CharField(max_length=30)
    course_name   = models.CharField(max_length=200, blank=True)
    lecturer_name = models.CharField(max_length=150, blank=True)
    lecturer      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='teaching_sessions')
    venue         = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='sessions')
    day_of_week   = models.IntegerField(choices=Day.choices)
    start_time    = models.TimeField()
    end_time      = models.TimeField()
    group         = models.CharField(max_length=20, blank=True)
    is_cross_cutting = models.BooleanField(default=False)
    is_active     = models.BooleanField(default=True)
    import_source = models.CharField(max_length=20, blank=True, default='manual')

    class Meta:
        db_table = 'timetable_sessions'
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f'{self.get_day_of_week_display()} {self.start_time:%H:%M} | {self.course_code} @ {self.venue.code}'


class TimetableImportLog(models.Model):
    imported_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    source           = models.CharField(max_length=10)
    filename         = models.CharField(max_length=255, blank=True)
    period           = models.ForeignKey(AcademicPeriod, on_delete=models.SET_NULL, null=True)
    status           = models.CharField(max_length=10)
    sessions_created = models.IntegerField(default=0)
    sessions_skipped = models.IntegerField(default=0)
    venues_created   = models.IntegerField(default=0)
    errors           = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'import_logs'
        ordering = ['-created_at']


class CancelledSession(models.Model):
    """CR cancels a session for a specific date — makes venue available."""
    session      = models.ForeignKey(TimetableSession, on_delete=models.CASCADE, related_name='cancellations')
    date         = models.DateField()
    cancelled_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cancelled_sessions')
    reason       = models.CharField(max_length=300, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cancelled_sessions'
        unique_together = [('session', 'date')]
        ordering = ['-date']

    def __str__(self):
        return f'{self.session.course_code} cancelled on {self.date} by {self.cancelled_by.full_name}'
