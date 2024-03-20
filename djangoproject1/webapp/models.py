from django.db import models

class UploadedImage(models.Model):
    """
    Model to store uploaded images.
    """
    # Define the image field to store uploaded images in the 'webapp/uploads/' directory
    image = models.ImageField(upload_to='webapp/uploads/')
    
    # Define a field to automatically store the time when the image was uploaded
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """
        Returns a string representation of the UploadedImage instance.
        """
        return self.name  # You're trying to access the 'name' attribute which is not defined in the model

