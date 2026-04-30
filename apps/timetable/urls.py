from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AcademicPeriodViewSet, CollegeViewSet, DepartmentViewSet,
    ProgramViewSet, TimetableSessionViewSet, ImportViewSet,
    CancelSessionViewSet, LecturerSessionsViewSet,
)

router = DefaultRouter()
router.register('periods',       AcademicPeriodViewSet,    basename='period')
router.register('colleges',      CollegeViewSet,            basename='college')
router.register('departments',   DepartmentViewSet,          basename='department')
router.register('programs',      ProgramViewSet,             basename='program')
router.register('sessions',      TimetableSessionViewSet,    basename='session')
router.register('import',        ImportViewSet,              basename='import')
router.register('cancellations', CancelSessionViewSet,       basename='cancellation')
router.register('lecturer',      LecturerSessionsViewSet,    basename='lecturer')
urlpatterns = [path('', include(router.urls))]
