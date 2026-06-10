from django.urls import include, path

urlpatterns = [
    path("theia/", include("theia_ng.urls")),
]
