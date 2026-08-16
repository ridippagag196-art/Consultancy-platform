from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.core.cache import cache
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Project, ProjectPhase, ProjectTask
from .serializers import (
    ProjectSerializer, ProjectListSerializer, 
    ProjectPhaseSerializer, ProjectTaskSerializer,
    ProjectDetailSerializer, ProjectCreateSerializer
)
from .filters import ProjectFilter
from .permissions import IsProjectMember
from .tasks import generate_project_report, sync_project_data

import logging
logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing projects with comprehensive CRUD operations
    """
    
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsProjectMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProjectFilter
    search_fields = ['name', 'description', 'project_code', 'client_name']
    ordering_fields = ['created_at', 'start_date', 'estimated_budget', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ProjectCreateSerializer
        elif self.action == 'list':
            return ProjectListSerializer
        elif self.action == 'retrieve':
            return ProjectDetailSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        """Filter projects based on user permissions"""
        user = self.request.user
        
        if user.is_superuser or user.is_staff:
            return Project.objects.all()
        
        # Users can see projects they manage or are on the team
        return Project.objects.filter(
            Q(project_manager=user) | Q(team_members=user)
        ).distinct()
    
    def perform_create(self, serializer):
        """Create project with current user as creator"""
        serializer.save(created_by=self.request.user)
        
    @action(detail=True, methods=['post'])
    def assign_team_member(self, request, pk=None):
        """Assign a team member to the project"""
        project = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Check if user is already assigned
            if project.team_members.filter(id=user_id).exists():
                return Response(
                    {'error': 'User already assigned to this project'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            project.team_members.add(user)
            
            # Log the assignment
            logger.info(f"User {user.email} assigned to project {project.project_code}")
            
            return Response(
                {'message': f'User {user.email} assigned to project successfully'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_team_member(self, request, pk=None):
        """Remove a team member from the project"""
        project = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Prevent removing the project manager
            if project.project_manager and project.project_manager.id == user_id:
                return Response(
                    {'error': 'Cannot remove project manager'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            project.team_members.remove(user)
            return Response(
                {'message': f'User {user.email} removed from project'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get project analytics and statistics"""
        project = self.get_object()
        
        # Get cached analytics if available
        cache_key = f'project_analytics_{project.id}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        # Calculate analytics
        tasks = project.tasks.all()
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='completed').count()
        
        total_estimated_hours = tasks.aggregate(Sum('estimated_hours'))['estimated_hours__sum'] or 0
        total_actual_hours = tasks.aggregate(Sum('actual_hours'))['actual_hours__sum'] or 0
        
        # Phase analytics
        phase_count = project.phases.count()
        completed_phases = project.phases.filter(status='completed').count()
        
        # Team analytics
        team_count = project.team_members.count()
        
        # Budget analytics
        total_budget = project.get_total_budget()
        total_spent = project.actual_cost
        
        analytics_data = {
            'project': {
                'id': str(project.id),
                'code': project.project_code,
                'name': project.name,
                'status': project.status,
                'progress': project.get_progress()
            },
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                'total_estimated_hours': float(total_estimated_hours),
                'total_actual_hours': float(total_actual_hours),
                'hours_variance': float(total_actual_hours - total_estimated_hours)
            },
            'phases': {
                'total': phase_count,
                'completed': completed_phases,
                'completion_rate': (completed_phases / phase_count * 100) if phase_count > 0 else 0
            },
            'team': {
                'total_members': team_count,
                'project_manager': project.project_manager.email if project.project_manager else None
            },
            'financial': {
                'estimated_budget': float(total_budget),
                'actual_cost': float(total_spent),
                'budget_variance': float(total_spent - total_budget),
                'budget_utilization': (total_spent / total_budget * 100) if total_budget > 0 else 0
            },
            'timeline': {
                'start_date': project.start_date.isoformat(),
                'estimated_end': project.estimated_end_date.isoformat() if project.estimated_end_date else None,
                'actual_end': project.actual_end_date.isoformat() if project.actual_end_date else None
            }
        }
        
        # Cache for 15 minutes
        cache.set(cache_key, analytics_data, 900)
        
        return Response(analytics_data)
    
    @action(detail=True, methods=['post'])
    def generate_report(self, request, pk=None):
        """Generate a project report"""
        project = self.get_object()
        report_type = request.data.get('report_type', 'summary')
        
        # Trigger async report generation
        task = generate_project_report.delay(str(project.id), report_type)
        
        return Response({
            'task_id': task.id,
            'status': 'processing',
            'message': f'Report generation started for {project.project_code}'
        })
    
    @action(detail=True, methods=['post'])
    def clone_project(self, request, pk=None):
        """Clone an existing project"""
        source_project = self.get_object()
        
        with transaction.atomic():
            # Create new project with same attributes
            new_project = Project(
                name=f"{source_project.name} (Clone)",
                description=source_project.description,
                project_type=source_project.project_type,
                client_name=source_project.client_name,
                client_contact=source_project.client_contact,
                client_email=source_project.client_email,
                client_phone=source_project.client_phone,
                client_address=source_project.client_address,
                location_name=source_project.location_name,
                location_description=source_project.location_description,
                location=source_project.location,
                start_date=source_project.start_date,
                estimated_budget=source_project.estimated_budget,
                billing_rate=source_project.billing_rate,
                project_manager=request.user,
                created_by=request.user
            )
            new_project.save()
            
            # Clone phases
            for phase in source_project.phases.all():
                new_phase = ProjectPhase(
                    project=new_project,
                    name=phase.name,
                    description=phase.description,
                    order=phase.order,
                    start_date=phase.start_date,
                    budget=phase.budget
                )
                new_phase.save()
            
            # Clone tasks
            for task in source_project.tasks.all():
                new_task = ProjectTask(
                    project=new_project,
                    title=task.title,
                    description=task.description,
                    priority=task.priority,
                    due_date=task.due_date,
                    estimated_hours=task.estimated_hours
                )
                new_task.save()
            
            logger.info(f"Project {source_project.project_code} cloned as {new_project.project_code}")
            
            return Response({
                'message': 'Project cloned successfully',
                'new_project_id': str(new_project.id),
                'new_project_code': new_project.project_code
            }, status=status.HTTP_201_CREATED)


class ProjectPhaseViewSet(viewsets.ModelViewSet):
    """ViewSet for project phases"""
    
    serializer_class = ProjectPhaseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        if project_id:
            return ProjectPhase.objects.filter(project_id=project_id)
        return ProjectPhase.objects.none()
    
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project)


class ProjectTaskViewSet(viewsets.ModelViewSet):
    """ViewSet for project tasks"""
    
    serializer_class = ProjectTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_pk')
        if project_id:
            return ProjectTask.objects.filter(project_id=project_id)
        return ProjectTask.objects.none()
    
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_pk')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None, project_pk=None):
        """Assign task to a user"""
        task = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Check if user is on project team
            if not task.project.team_members.filter(id=user_id).exists():
                return Response(
                    {'error': 'User is not a team member of this project'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            task.assigned_to = user
            task.save()
            
            return Response({
                'message': f'Task assigned to {user.email}',
                'task_id': str(task.id)
            })
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )