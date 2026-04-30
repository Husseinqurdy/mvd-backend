from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Building, Venue
from .venue_status import get_venue_status, get_all_statuses, get_today_sessions
from apps.accounts.views import IsAdminOrReadOnly


class BuildingSerializer(serializers.ModelSerializer):
    venue_count = serializers.SerializerMethodField()
    class Meta:
        model  = Building
        fields = ['id', 'name', 'code', 'location', 'venue_count']
    def get_venue_count(self, obj):
        return obj.venues.filter(is_active=True).count()


class VenueSerializer(serializers.ModelSerializer):
    building_name      = serializers.CharField(source='building.name', read_only=True)
    venue_type_display = serializers.CharField(source='get_venue_type_display', read_only=True)
    class Meta:
        model  = Venue
        fields = ['id', 'building', 'building_name', 'name', 'code',
                  'venue_type', 'venue_type_display', 'capacity', 'wing', 'is_active']


class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = [IsAdminOrReadOnly]


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.select_related('building').all()
    serializer_class = VenueSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields  = ['building', 'venue_type', 'is_active']
    search_fields     = ['name', 'code']

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='status')
    def all_status(self, request):
        """Real-time status for ALL venues — used by admin/CR overview."""
        return Response(get_all_statuses())

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='today')
    def today_sessions(self, request):
        """
        All sessions scheduled for TODAY — used by TV Display.
        Much more useful than showing all venues.
        """
        return Response(get_today_sessions())

    @action(detail=True, methods=['get'], permission_classes=[AllowAny], url_path='status')
    def single_status(self, request, pk=None):
        return Response(get_venue_status(self.get_object()))
