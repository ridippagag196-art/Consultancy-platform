from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from apps.projects.models import Project
import uuid

User = get_user_model()

class SurveyPoint(models.Model):
    """Geospatial survey point with field data"""
    
    class PointType(models.TextChoices):
        GCN = 'gcn', 'Geodetic Control Network'
        BOUNDARY = 'boundary', 'Boundary'
        TOPOGRAPHIC = 'topographic', 'Topographic'
        FEATURE = 'feature', 'Feature'
        TRAVERSE = 'traverse', 'Traverse'
        BUILDING = 'building', 'Building'
        UTILITY = 'utility', 'Utility'
        OTHER = 'other', 'Other'
    
    class PointStatus(models.TextChoices):
        SURVEYED = 'surveyed', 'Surveyed'
        UNCONFIRMED = 'unconfirmed', 'Unconfirmed'
        REJECTED = 'rejected', 'Rejected'
        ADJUSTED = 'adjusted', 'Adjusted'
        DELETED = 'deleted', 'Deleted'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='survey_points')
    
    # Point Identification
    point_number = models.CharField(max_length=50)
    point_name = models.CharField(max_length=255, blank=True)
    point_type = models.CharField(max_length=20, choices=PointType.choices)
    
    # Geospatial Data
    geometry = gis_models.PointField(srid=4326)
    elevation = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    accuracy_h = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    accuracy_v = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    
    # Field Data
    field_notes = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=PointStatus.choices, default=PointStatus.UNCONFIRMED)
    
    # Survey Metadata
    survey_date = models.DateField()
    survey_time = models.TimeField(null=True, blank=True)
    instrument_type = models.CharField(max_length=100, blank=True)
    instrument_serial = models.CharField(max_length=50, blank=True)
    surveyor = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='surveyed_points'
    )
    
    # Photos and Attachments
    photos = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    # Adjustment Data
    adjusted_geometry = gis_models.PointField(srid=4326, null=True, blank=True)
    adjustment_residuals = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='created_survey_points'
    )
    
    class Meta:
        unique_together = ['project', 'point_number']
        indexes = [
            models.Index(fields=['project', 'point_number']),
            models.Index(fields=['point_type']),
            models.Index(fields=['survey_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.point_number} - {self.point_name or 'Unnamed'}"
    
    def get_coordinates(self):
        """Return coordinates as [longitude, latitude]"""
        return [self.geometry.x, self.geometry.y]
    
    def get_elevation_display(self):
        """Format elevation with units"""
        if self.elevation:
            return f"{self.elevation:.3f}m"
        return "N/A"


class SurveyTraverse(models.Model):
    """Survey traverse for network adjustment"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='traverses')
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    points = models.ManyToManyField(SurveyPoint, through='TraversePoint', related_name='traverses')
    
    start_point = models.ForeignKey(
        SurveyPoint, on_delete=models.SET_NULL,
        null=True, related_name='traverse_starts'
    )
    end_point = models.ForeignKey(
        SurveyPoint, on_delete=models.SET_NULL,
        null=True, related_name='traverse_ends'
    )
    
    total_distance = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    closure_error = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    adjustment_status = models.CharField(max_length=20, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class TraversePoint(models.Model):
    """Through model for traverse point order"""
    
    traverse = models.ForeignKey(SurveyTraverse, on_delete=models.CASCADE)
    point = models.ForeignKey(SurveyPoint, on_delete=models.CASCADE)
    order = models.IntegerField()
    
    distance = models.DecimalField(max_digits=10, decimal_places=3)
    bearing = models.DecimalField(max_digits=10, decimal_places=6)
    
    class Meta:
        ordering = ['order']
        unique_together = ['traverse', 'order']


class SurveyImage(models.Model):
    """Survey photos with geotagging"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_point = models.ForeignKey(
        SurveyPoint, on_delete=models.CASCADE,
        related_name='images'
    )
    
    image = models.ImageField(upload_to='survey_photos/%Y/%m/%d/')
    thumbnail = models.ImageField(upload_to='survey_photos/thumbnails/', null=True, blank=True)
    
    description = models.CharField(max_length=255, blank=True)
    captured_at = models.DateTimeField()
    gps_location = gis_models.PointField(srid=4326, null=True, blank=True)
    
    camera_model = models.CharField(max_length=100, blank=True)
    camera_settings = models.JSONField(default=dict, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_images'
    )
    
    def __str__(self):
        return f"Image for {self.survey_point.point_number} - {self.captured_at}"