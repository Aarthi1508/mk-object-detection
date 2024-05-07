# urls.py

from django.urls import path
from .views import image_upload, upload_to_s3, uploaded_page, detect_object, detected_image_page, image_details_popup, assignment_view, get_images

urlpatterns = [
    path('upload/', image_upload, name='image_upload'),
    path('upload-to-s3/', upload_to_s3, name='upload_to_s3'),
    path('uploaded_page/', uploaded_page, name='uploaded_page'),
    path('detect-object/', detect_object, name='detect_object'),
    path('detected_image_page/', detected_image_page, name='detected_image_page'),    
    path('image_details/', image_details_popup, name='image_details_popup'),
    path('assignment/', assignment_view, name='assignment'),
    path('get_images/', get_images, name='get_images'),
]
