from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VenueRequestViewSet

router = DefaultRouter()
router.register('', VenueRequestViewSet, basename='venuerequest')
urlpatterns = [path('', include(router.urls))]
