from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BuildingViewSet, VenueViewSet

router = DefaultRouter()
router.register('buildings', BuildingViewSet, basename='building')
router.register('', VenueViewSet, basename='venue')
urlpatterns = [path('', include(router.urls))]
