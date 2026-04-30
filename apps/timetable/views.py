from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from .models import AcademicPeriod, College, Department, Program, TimetableSession, TimetableImportLog
from apps.accounts.views import IsAdmin, IsAdminOrReadOnly


# ── Serializers ───────────────────────────────────────────────────────────────

class AcademicPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AcademicPeriod
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active']


class CollegeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = College
        fields = ['id', 'name', 'code']


class DepartmentSerializer(serializers.ModelSerializer):
    college_name = serializers.CharField(source='college.name', read_only=True)
    class Meta:
        model  = Department
        fields = ['id', 'name', 'code', 'college', 'college_name']


class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    college_name    = serializers.CharField(source='department.college.name', read_only=True)
    class Meta:
        model  = Program
        fields = ['id', 'name', 'code', 'level', 'uqf_level', 'duration_years',
                  'department', 'department_name', 'college_name']


class SessionSerializer(serializers.ModelSerializer):
    venue_code   = serializers.CharField(source='venue.code', read_only=True)
    venue_name   = serializers.CharField(source='venue.name', read_only=True)
    building     = serializers.CharField(source='venue.building.name', read_only=True)
    day_display  = serializers.CharField(source='get_day_of_week_display', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True, allow_null=True)
    class Meta:
        model  = TimetableSession
        fields = [
            'id', 'period', 'program', 'program_name', 'year_of_study',
            'course_code', 'course_name', 'lecturer_name', 'lecturer',
            'venue', 'venue_code', 'venue_name', 'building',
            'day_of_week', 'day_display', 'start_time', 'end_time',
            'group', 'is_cross_cutting', 'is_active', 'import_source',
        ]


class ImportLogSerializer(serializers.ModelSerializer):
    imported_by_name = serializers.CharField(source='imported_by.full_name', read_only=True, allow_null=True)
    period_name      = serializers.CharField(source='period.name', read_only=True, allow_null=True)
    class Meta:
        model  = TimetableImportLog
        fields = ['id', 'source', 'filename', 'status', 'sessions_created',
                  'sessions_skipped', 'venues_created', 'errors',
                  'imported_by_name', 'period_name', 'created_at']


# ── ViewSets ──────────────────────────────────────────────────────────────────

class AcademicPeriodViewSet(viewsets.ModelViewSet):
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin], url_path='set-active')
    def set_active(self, request, pk=None):
        period = self.get_object()
        AcademicPeriod.objects.exclude(pk=period.pk).update(is_active=False)
        period.is_active = True
        period.save()
        return Response(AcademicPeriodSerializer(period).data)


class CollegeViewSet(viewsets.ModelViewSet):
    queryset = College.objects.all()
    serializer_class = CollegeSerializer
    permission_classes = [IsAdminOrReadOnly]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('college').all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['college']


class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.select_related('department__college').all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['department', 'level']
    search_fields = ['name', 'code']


class TimetableSessionViewSet(viewsets.ModelViewSet):
    queryset = TimetableSession.objects.select_related(
        'venue', 'venue__building', 'lecturer', 'period', 'program'
    ).all()
    serializer_class = SessionSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields  = ['period', 'venue', 'day_of_week', 'program', 'is_active']
    search_fields     = ['course_code', 'course_name', 'lecturer_name']
    ordering_fields   = ['day_of_week', 'start_time']


class ImportViewSet(viewsets.ViewSet):
    permission_classes = [IsAdmin]
    parser_classes     = [MultiPartParser, FormParser]

    @action(detail=False, methods=['post'], url_path='pdf')
    def upload_pdf(self, request):
        return self._handle(request, 'pdf')

    @action(detail=False, methods=['post'], url_path='excel')
    def upload_excel(self, request):
        return self._handle(request, 'excel')

    @action(detail=False, methods=['post'], url_path='csv')
    def upload_csv(self, request):
        return self._handle(request, 'csv')

    @action(detail=False, methods=['get'], url_path='template')
    def template(self, request):
        from .parsers.excel_parser import generate_template
        resp = HttpResponse(
            generate_template(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resp['Content-Disposition'] = 'attachment; filename="timetable_template.xlsx"'
        return resp

    @action(detail=False, methods=['get'], url_path='logs')
    def logs(self, request):
        qs = TimetableImportLog.objects.all()[:50]
        return Response(ImportLogSerializer(qs, many=True).data)

    @action(detail=False, methods=['delete'], url_path='logs/delete/(?P<log_id>[0-9]+)')
    def delete_log(self, request, log_id=None):
        try:
            log = TimetableImportLog.objects.get(pk=log_id)
            log.delete()
            return Response({'detail': 'Log deleted.'}, status=204)
        except TimetableImportLog.DoesNotExist:
            return Response({'detail': 'Log not found.'}, status=404)

    @action(detail=False, methods=['delete'], url_path='logs/clear')
    def clear_logs(self, request):
        count, _ = TimetableImportLog.objects.all().delete()
        return Response({'detail': f'{count} log(s) deleted.'})

    def _handle(self, request, source):
        file      = request.FILES.get('file')
        period_id = request.data.get('period_id')
        replace   = str(request.data.get('replace', 'false')).lower() == 'true'

        if not file:
            return Response({'detail': 'No file.'}, status=400)
        if not period_id:
            return Response({'detail': 'period_id required.'}, status=400)

        try:
            period = AcademicPeriod.objects.get(pk=period_id)
        except AcademicPeriod.DoesNotExist:
            return Response({'detail': 'Period not found.'}, status=404)

        data = file.read()
        try:
            if source == 'pdf':
                from .parsers.pdf_parser import parse_pdf
                from .parsers.importer import import_pdf
                pages = parse_pdf(data)
                if not pages:
                    return Response({'detail': 'PDF parsed but no timetable pages found.'}, status=400)
                summary = import_pdf(pages, period, request.user, replace=replace)
            else:
                from .parsers.importer import import_excel
                if source == 'excel':
                    from .parsers.excel_parser import parse_excel
                    rows = parse_excel(data)
                else:
                    from .parsers.excel_parser import parse_csv
                    rows = parse_csv(data)
                if not rows:
                    return Response({'detail': f'No valid rows found in {source.upper()}.'}, status=400)
                summary = import_excel(rows, period, request.user, source=source, replace=replace)
        except ImportError as e:
            return Response({'detail': str(e)}, status=500)
        except Exception as e:
            return Response({'detail': f'Import error: {e}'}, status=500)

        return Response({
            'status':           'success' if not summary['errors'] else 'partial',
            'sessions_created': summary['sessions_created'],
            'sessions_skipped': summary['sessions_skipped'],
            'venues_created':   summary['venues_created'],
            'errors':           summary['errors'][:10],
            'message':          f"Created {summary['sessions_created']} sessions, {summary['venues_created']} new venues.",
        })


# ── CancelledSession ─────────────────────────────────────────────────────────

class CancelledSessionSerializer(serializers.ModelSerializer):
    course_code  = serializers.CharField(source='session.course_code', read_only=True)
    venue_code   = serializers.CharField(source='session.venue.code', read_only=True)
    cancelled_by_name = serializers.CharField(source='cancelled_by.full_name', read_only=True)

    class Meta:
        model  = __import__('apps.timetable.models', fromlist=['CancelledSession']).CancelledSession
        fields = ['id', 'session', 'course_code', 'venue_code',
                  'date', 'reason', 'cancelled_by', 'cancelled_by_name', 'created_at']
        read_only_fields = ['id', 'cancelled_by', 'created_at']


class CancelSessionViewSet(viewsets.ViewSet):
    """CR can cancel a session for a specific date (makes venue available). Admin can also restore it."""
    from apps.accounts.views import IsAdmin

    def get_permissions(self):
        return [__import__('rest_framework.permissions', fromlist=['IsAuthenticated']).IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel(self, request):
        from apps.timetable.models import TimetableSession, CancelledSession
        session_id = request.data.get('session_id')
        date_str   = request.data.get('date')
        reason     = request.data.get('reason', '')

        if not session_id or not date_str:
            return Response({'detail': 'session_id and date required.'}, status=400)

        try:
            session = TimetableSession.objects.get(pk=session_id)
        except TimetableSession.DoesNotExist:
            return Response({'detail': 'Session not found.'}, status=404)

        from datetime import date
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            return Response({'detail': 'Invalid date. Use YYYY-MM-DD.'}, status=400)

        obj, created = CancelledSession.objects.get_or_create(
            session=session, date=d,
            defaults={'cancelled_by': request.user, 'reason': reason},
        )
        if not created:
            return Response({'detail': 'Session already cancelled for this date.'}, status=400)

        return Response({
            'detail': f'{session.course_code} on {d} marked as cancelled. Venue {session.venue.code} is now available.',
            'cancelled_id': obj.id,
        })

    @action(detail=False, methods=['post'], url_path='restore')
    def restore(self, request):
        from apps.timetable.models import CancelledSession
        from datetime import date
        session_id = request.data.get('session_id')
        date_str   = request.data.get('date')
        if not session_id or not date_str:
            return Response({'detail': 'session_id and date required.'}, status=400)
        try:
            d   = date.fromisoformat(date_str)
            obj = CancelledSession.objects.get(session_id=session_id, date=d)
        except (ValueError, CancelledSession.DoesNotExist):
            return Response({'detail': 'Cancellation not found.'}, status=404)

        if request.user.role != 'ADMIN' and obj.cancelled_by != request.user:
            return Response({'detail': 'Permission denied.'}, status=403)

        obj.delete()
        return Response({'detail': 'Session restored. Venue is back to occupied.'})

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        from apps.timetable.models import CancelledSession
        from django.utils import timezone
        today = timezone.localdate()
        qs = CancelledSession.objects.filter(date=today).select_related(
            'session', 'session__venue', 'cancelled_by'
        )
        return Response(CancelledSessionSerializer(qs, many=True).data)


class LecturerSessionsViewSet(viewsets.ViewSet):
    """Returns timetable sessions for the logged-in lecturer, matched by lecturer_name."""

    def get_permissions(self):
        return [__import__('rest_framework.permissions', fromlist=['IsAuthenticated']).IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='my-sessions')
    def my_sessions(self, request):
        """
        GET /api/timetable/lecturer/my-sessions/
        Improved name matching with deduplication to prevent double sessions.
        """
        from apps.timetable.models import TimetableSession, AcademicPeriod
        from django.db.models import Q

        user = request.user
        name_parts = user.full_name.strip().split()

        # Strategy: match full name, then only parts longer than 2 chars.
        # This prevents single-letter initials like "D" from matching everyone.
        # e.g. "Bynite D" -> matches "Bynite" (5 chars) but NOT "D" (1 char)
        queries = Q(lecturer_name__icontains=user.full_name)
        for part in name_parts:
            if len(part) > 2:
                queries |= Q(lecturer_name__icontains=part)

        try:
            period = AcademicPeriod.objects.get(is_active=True)
        except AcademicPeriod.DoesNotExist:
            return Response([])

        sessions = TimetableSession.objects.filter(
            period=period, is_active=True,
        ).filter(queries).select_related('venue', 'venue__building', 'program').order_by('day_of_week', 'start_time')

        # Deduplicate by (course_code, venue, day, start_time, end_time)
        seen = set()
        result = []
        for s in sessions:
            key = (s.course_code, s.venue_id, s.day_of_week,
                   s.start_time.strftime('%H:%M'), s.end_time.strftime('%H:%M'))
            if key in seen:
                continue
            seen.add(key)
            result.append({
                'id':            s.id,
                'course_code':   s.course_code,
                'course_name':   s.course_name,
                'day_of_week':   s.day_of_week,
                'day_display':   s.get_day_of_week_display(),
                'start_time':    s.start_time.strftime('%H:%M'),
                'end_time':      s.end_time.strftime('%H:%M'),
                'venue_code':    s.venue.code,
                'venue_name':    s.venue.name,
                'building':      s.venue.building.name,
                'program_name':  s.program.name if s.program else '',
                'year':          s.year_of_study,
                'group':         s.group,
                'lecturer_name': s.lecturer_name,
            })
        return Response(result)
