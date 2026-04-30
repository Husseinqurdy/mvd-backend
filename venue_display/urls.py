from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/',   CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(),          name='token_refresh'),
    path('api/accounts/',  include('apps.accounts.urls')),
    path('api/venues/',    include('apps.venues.urls')),
    path('api/timetable/', include('apps.timetable.urls')),
    path('api/requests/',  include('apps.requests.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
