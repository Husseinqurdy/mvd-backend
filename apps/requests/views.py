from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import VenueRequest
from apps.accounts.views import IsAdmin


class VenueRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    reviewed_by_name  = serializers.CharField(source='reviewed_by.full_name',  read_only=True, allow_null=True)
    venue_code        = serializers.CharField(source='venue.code', read_only=True)
    venue_name        = serializers.CharField(source='venue.name', read_only=True)
    building_name     = serializers.CharField(source='venue.building.name', read_only=True)
    capacity          = serializers.IntegerField(source='venue.capacity', read_only=True)

    class Meta:
        model  = VenueRequest
        fields = [
            'id', 'venue', 'venue_code', 'venue_name', 'building_name', 'capacity',
            'requested_by', 'requested_by_name',
            'reviewed_by', 'reviewed_by_name',
            'purpose', 'date', 'start_time', 'end_time', 'attendees',
            'status', 'admin_note', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'requested_by', 'reviewed_by', 'status', 'admin_note', 'created_at', 'updated_at']


class ReviewSerializer(serializers.Serializer):
    action     = serializers.ChoiceField(choices=['approve', 'reject'])
    admin_note = serializers.CharField(required=False, allow_blank=True, default='')


class VenueRequestViewSet(viewsets.ModelViewSet):
    serializer_class = VenueRequestSerializer

    def get_permissions(self):
        if self.action == 'review':
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs   = VenueRequest.objects.select_related(
            'venue', 'venue__building', 'requested_by', 'reviewed_by'
        )
        if user.role == 'ADMIN':
            status = self.request.query_params.get('status')
            if status:
                qs = qs.filter(status=status)
            return qs.all()
        return qs.filter(requested_by=user)

    def perform_create(self, serializer):
        """
        Auto-confirm if venue is AVAILABLE at the requested time.
        If there's a conflict, set PENDING for manual admin review.
        """
        req_data = serializer.validated_data
        venue    = req_data['venue']
        date     = req_data['date']
        start    = req_data['start_time']
        end      = req_data['end_time']

        conflict = _find_conflict_raw(venue, date, start, end)
        if conflict:
            # Venue busy — pending for admin
            serializer.save(
                requested_by=self.request.user,
                status='PENDING',
                admin_note='Awaiting admin approval — possible conflict detected.',
            )
        else:
            # Venue is free — auto-approve
            serializer.save(
                requested_by=self.request.user,
                reviewed_by=self.request.user,   # self-reviewed (auto)
                status='APPROVED',
                admin_note='Auto-confirmed: venue was available at requested time.',
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def review(self, request, pk=None):
        req = self.get_object()
        if req.status != 'PENDING':
            return Response({'detail': 'Only pending requests can be reviewed.'}, status=400)

        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        if s.validated_data['action'] == 'approve':
            conflict = _find_conflict(req)
            if conflict:
                return Response({'detail': f'Time conflict with: {conflict}'}, status=400)
            req.status = 'APPROVED'
        else:
            req.status = 'REJECTED'

        req.admin_note  = s.validated_data['admin_note']
        req.reviewed_by = request.user
        req.save()
        return Response(VenueRequestSerializer(req).data)


def _find_conflict_raw(venue, date, start_time, end_time, exclude_pk=None):
    """Check conflict in VenueRequest table."""
    conflicts = VenueRequest.objects.filter(
        venue=venue, date=date, status='APPROVED'
    )
    if exclude_pk:
        conflicts = conflicts.exclude(pk=exclude_pk)
    for c in conflicts:
        if start_time < c.end_time and end_time > c.start_time:
            return f'Request #{c.id} ({c.start_time:%H:%M}–{c.end_time:%H:%M})'

    # Also check timetable sessions
    from apps.timetable.models import TimetableSession, AcademicPeriod, CancelledSession
    import datetime
    weekday = date.isoweekday()
    try:
        period = AcademicPeriod.objects.get(is_active=True)
        sessions = TimetableSession.objects.filter(
            venue=venue, period=period,
            day_of_week=weekday, is_active=True,
        )
        for s in sessions:
            if CancelledSession.objects.filter(session=s, date=date).exists():
                continue
            if start_time < s.end_time and end_time > s.start_time:
                return f'Timetable: {s.course_code} ({s.start_time:%H:%M}–{s.end_time:%H:%M})'
    except AcademicPeriod.DoesNotExist:
        pass
    return None


def _find_conflict(req):
    return _find_conflict_raw(req.venue, req.date, req.start_time, req.end_time, exclude_pk=req.pk)
