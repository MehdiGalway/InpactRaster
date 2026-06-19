from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/rasters/", views.raster_catalog, name="raster_catalog"),
    path("api/raster/meta/", views.raster_meta, name="raster_meta"),
    path("api/raster/image/", views.raster_image, name="raster_image"),
    path("api/feedback/", views.submit_feedback, name="submit_feedback"),
    path("api/feedback/download/", views.download_feedback, name="download_feedback"),
]
