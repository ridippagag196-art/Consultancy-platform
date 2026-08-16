from django.db import models
from django.contrib.gis.db import models as gis_models
from apps.projects.models import Project
import uuid

class Borehole(models.Model):
    """Borehole investigation data"""
    
    class DrillingMethod(models.TextChoices):
        AUGER = 'auger', 'Auger Drilling'
        ROTARY = 'rotary', 'Rotary Drilling'
        PERCUSSION = 'percussion', 'Percussion Drilling'
        SONIC = 'sonic', 'Sonic Drilling'
        DIAMOND = 'diamond', 'Diamond Core Drilling'
    
    class GroundwaterCondition(models.TextChoices):
        DRY = 'dry', 'Dry'
        DAMP = 'damp', 'Damp'
        WET = 'wet', 'Wet'
        WATER_TABLE = 'water_table', 'Water Table Encountered'
        ARTESIAN = 'artesian', 'Artesian'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='boreholes')
    
    borehole_id = models.CharField(max_length=50)
    location = gis_models.PointField(srid=4326)
    
    # Borehole Details
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    total_depth = models.DecimalField(max_digits=8, decimal_places=2)  # meters
    
    drilling_method = models.CharField(max_length=20, choices=DrillingMethod.choices)
    drilling_contractor = models.CharField(max_length=255, blank=True)
    
    # Ground Conditions
    groundwater_level = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    groundwater_condition = models.CharField(
        max_length=20, 
        choices=GroundwaterCondition.choices,
        default=GroundwaterCondition.DRY
    )
    
    # Equipment
    casing_type = models.CharField(max_length=100, blank=True)
    casing_diameter = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    bit_size = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Geological Data
    rock_quality_designation = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    core_recovery = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Metadata
    field_notes = models.TextField(blank=True)
    photos = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, related_name='created_boreholes'
    )
    
    class Meta:
        unique_together = ['project', 'borehole_id']
        indexes = [
            models.Index(fields=['project', 'borehole_id']),
            models.Index(fields=['start_date']),
            models.Index(fields=['total_depth']),
        ]
    
    def __str__(self):
        return f"{self.borehole_id} - Depth: {self.total_depth}m"


class SoilLayer(models.Model):
    """Soil/rock layers from borehole logging"""
    
    class SoilType(models.TextChoices):
        TOPSOIL = 'topsoil', 'Topsoil'
        CLAY = 'clay', 'Clay'
        SILT = 'silt', 'Silt'
        SAND = 'sand', 'Sand'
        GRAVEL = 'gravel', 'Gravel'
        COBBLE = 'cobble', 'Cobble'
        BOULDER = 'boulder', 'Boulder'
        WEATHERED_ROCK = 'weathered_rock', 'Weathered Rock'
        ROCK = 'rock', 'Rock'
        FILL = 'fill', 'Fill Material'
        OTHER = 'other', 'Other'
    
    class Consistency(models.TextChoices):
        VERY_SOFT = 'very_soft', 'Very Soft'
        SOFT = 'soft', 'Soft'
        MEDIUM = 'medium', 'Medium'
        STIFF = 'stiff', 'Stiff'
        VERY_STIFF = 'very_stiff', 'Very Stiff'
        HARD = 'hard', 'Hard'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    borehole = models.ForeignKey(Borehole, on_delete=models.CASCADE, related_name='layers')
    
    # Layer boundaries
    top_depth = models.DecimalField(max_digits=8, decimal_places=2)
    bottom_depth = models.DecimalField(max_digits=8, decimal_places=2)
    thickness = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Soil Description
    soil_type = models.CharField(max_length=20, choices=SoilType.choices)
    soil_description = models.TextField()
    
    # Color
    color = models.CharField(max_length=50, blank=True)
    color_munsell = models.CharField(max_length=20, blank=True)
    
    # Physical Properties
    consistency = models.CharField(max_length=20, choices=Consistency.choices, null=True, blank=True)
    moisture = models.CharField(max_length=50, blank=True)  # Dry, damp, wet, etc.
    plasticity = models.CharField(max_length=50, blank=True)  # Non-plastic, low, medium, high
    
    # Stratigraphy
    geological_formation = models.CharField(max_length=255, blank=True)
    geological_age = models.CharField(max_length=100, blank=True)
    
    # Sample Information
    samples_taken = models.BooleanField(default=False)
    sample_numbers = models.JSONField(default=list, blank=True)
    
    # Field Tests
    standard_penetration_test = models.JSONField(default=dict, blank=True)  # N-values
    field_shear_test = models.JSONField(default=dict, blank=True)
    
    # Metadata
    field_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['top_depth']
        indexes = [
            models.Index(fields=['borehole', 'top_depth']),
            models.Index(fields=['soil_type']),
        ]
    
    def __str__(self):
        return f"{self.borehole.borehole_id} - {self.soil_type} ({self.top_depth}m - {self.bottom_depth}m)"
    
    def save(self, *args, **kwargs):
        # Auto-calculate thickness
        if self.bottom_depth and self.top_depth:
            self.thickness = self.bottom_depth - self.top_depth
        super().save(*args, **kwargs)


class LabTest(models.Model):
    """Laboratory test results for soil samples"""
    
    class TestType(models.TextChoices):
        MOISTURE_CONTENT = 'moisture_content', 'Moisture Content'
        ATTERBERG_LIMITS = 'atterberg_limits', 'Atterberg Limits'
        GRAIN_SIZE = 'grain_size', 'Grain Size Analysis'
        SPECIFIC_GRAVITY = 'specific_gravity', 'Specific Gravity'
        COMPACTION = 'compaction', 'Compaction Test'
        UNCONFINED_COMPRESSION = 'unconfined_compression', 'Unconfined Compression'
        TRIAXIAL = 'triaxial', 'Triaxial Test'
        CONSOLIDATION = 'consolidation', 'Consolidation Test'
        PERMEABILITY = 'permeability', 'Permeability Test'
        CHEMICAL = 'chemical', 'Chemical Analysis'
        OTHER = 'other', 'Other'
    
    class TestStatus(models.TextChoices):
        SAMPLED = 'sampled', 'Sampled'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layer = models.ForeignKey(SoilLayer, on_delete=models.CASCADE, related_name='lab_tests')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='lab_tests')
    
    test_type = models.CharField(max_length=30, choices=TestType.choices)
    test_name = models.CharField(max_length=255)
    test_status = models.CharField(max_length=20, choices=TestStatus.choices, default=TestStatus.SAMPLED)
    
    sample_id = models.CharField(max_length=50)
    sample_depth = models.DecimalField(max_digits=8, decimal_places=2)
    sample_weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    
    # Results
    test_results = models.JSONField(default=dict)
    test_report = models.FileField(upload_to='lab_reports/%Y/%m/%d/', null=True, blank=True)
    results_summary = models.TextField(blank=True)
    
    # Laboratory Information
    lab_name = models.CharField(max_length=255)
    lab_contact = models.CharField(max_length=100, blank=True)
    test_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    certified_by = models.CharField(max_length=255, blank=True)
    
    # Quality Control
    qc_verified = models.BooleanField(default=False)
    qc_verified_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_tests'
    )
    qc_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, related_name='created_lab_tests'
    )
    
    def __str__(self):
        return f"{self.sample_id} - {self.get_test_type_display()}"