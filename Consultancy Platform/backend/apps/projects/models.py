from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal
import uuid

User = get_user_model()

class Project(models.Model):
    """Core project model with geospatial capabilities"""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        ON_HOLD = 'on_hold', 'On Hold'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        ARCHIVED = 'archived', 'Archived'
    
    class ProjectType(models.TextChoices):
        CONSULTANCY = 'consultancy', 'Consultancy'
        SURVEY = 'survey', 'Survey'
        GEOTECHNICAL = 'geotechnical', 'Geotechnical Investigation'
        DESIGN = 'design', 'Design'
        BIM = 'bim', 'BIM Modeling'
        CONSTRUCTION = 'construction', 'Construction'
        OTHER = 'other', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Client Information
    client_name = models.CharField(max_length=255)
    client_contact = models.CharField(max_length=100)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=20)
    client_address = models.TextField(blank=True)
    
    # Location Information
    location_name = models.CharField(max_length=255)
    location_description = models.TextField(blank=True)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    location_geometry = gis_models.GeometryField(srid=4326, null=True, blank=True)
    bounding_box = gis_models.PolygonField(srid=4326, null=True, blank=True)
    
    # Project Dates
    start_date = models.DateField()
    estimated_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Budget & Financial
    estimated_budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    billing_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Team
    project_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='managed_projects'
    )
    team_members = models.ManyToManyField(
        User, blank=True, 
        related_name='projects'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, related_name='created_projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)
    
    # Custom Fields (JSON)
    custom_metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['project_code']),
            models.Index(fields=['status']),
            models.Index(fields=['client_name']),
            models.Index(fields=['start_date']),
            models.Index(fields=['project_type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project_code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.project_code:
            # Generate project code: PRJ-YYYY-XXXX
            year = timezone.now().year
            last_project = Project.objects.filter(
                project_code__startswith=f'PRJ-{year}'
            ).order_by('-created_at').first()
            
            if last_project:
                last_num = int(last_project.project_code.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.project_code = f"PRJ-{year}-{new_num:04d}"
        
        super().save(*args, **kwargs)
    
    def get_total_budget(self):
        """Calculate total budget including all phases"""
        total = self.estimated_budget
        for phase in self.phases.all():
            total += phase.budget
        return total
    
    def get_progress(self):
        """Calculate project progress percentage"""
        if self.status == self.Status.COMPLETED:
            return 100
        
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            return 0
        
        completed_tasks = self.tasks.filter(status='completed').count()
        return int((completed_tasks / total_tasks) * 100)


class ProjectPhase(models.Model):
    """Project phases for better organization"""
    
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        DELAYED = 'delayed', 'Delayed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='phases')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField()
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    responsible = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['project', 'order']
    
    def __str__(self):
        return f"{self.project.project_code} - {self.name}"


class ProjectTask(models.Model):
    """Detailed task management"""
    
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        REVIEW = 'review', 'In Review'
        COMPLETED = 'completed', 'Completed'
        BLOCKED = 'blocked', 'Blocked'
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    phase = models.ForeignKey(ProjectPhase, on_delete=models.SET_NULL, null=True, blank=True)
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_tasks'
    )
    
    due_date = models.DateField()
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    parent_task = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='subtasks'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Dependencies
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)