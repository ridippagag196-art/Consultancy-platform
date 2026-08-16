from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q
import logging
from datetime import timedelta
import json

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_project_report(self, project_id, report_type='summary'):
    """
    Generate a comprehensive project report asynchronously
    """
    from .models import Project
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Gather report data
        report_data = {
            'project': project,
            'tasks': project.tasks.all(),
            'phases': project.phases.all(),
            'survey_points': project.survey_points.all() if hasattr(project, 'survey_points') else [],
            'boreholes': project.boreholes.all() if hasattr(project, 'boreholes') else [],
            'generated_at': timezone.now().isoformat(),
            'report_type': report_type
        }
        
        # Generate report based on type
        if report_type == 'summary':
            report_content = generate_summary_report(report_data)
        elif report_type == 'detailed':
            report_content = generate_detailed_report(report_data)
        elif report_type == 'geotechnical':
            report_content = generate_geotechnical_report(report_data)
        else:
            report_content = generate_summary_report(report_data)
        
        # Save report to database or file storage
        # Implementation depends on your storage strategy
        
        return {
            'status': 'success',
            'project_id': project_id,
            'report_type': report_type,
            'report_content': report_content[:1000]  # Truncate for demo
        }
        
    except Project.DoesNotExist:
        logger.error(f"Project {project_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        self.retry(exc=e, countdown=60 * 5)  # Retry in 5 minutes


def generate_summary_report(report_data):
    """Generate a summary report"""
    project = report_data['project']
    tasks = report_data['tasks']
    phases = report_data['phases']
    
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        'title': f"Project Summary - {project.project_code}",
        'project_info': {
            'name': project.name,
            'client': project.client_name,
            'status': project.status,
            'progress': project.get_progress()
        },
        'summary': {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': f"{completion_percentage:.1f}%",
            'total_phases': phases.count()
        },
        'financial': {
            'budget': float(project.estimated_budget),
            'actual_cost': float(project.actual_cost)
        }
    }


def generate_detailed_report(report_data):
    """Generate a detailed report with all project data"""
    project = report_data['project']
    tasks = report_data['tasks']
    phases = report_data['phases']
    
    return {
        'title': f"Detailed Project Report - {project.project_code}",
        'project_info': {
            'name': project.name,
            'code': project.project_code,
            'client': project.client_name,
            'contact': project.client_contact,
            'email': project.client_email,
            'start_date': project.start_date.isoformat(),
            'status': project.status
        },
        'phases': [
            {
                'name': phase.name,
                'status': phase.status,
                'budget': float(phase.budget),
                'tasks_count': phase.projecttask_set.count()
            }
            for phase in phases
        ],
        'tasks': [
            {
                'title': task.title,
                'priority': task.priority,
                'status': task.status,
                'assigned_to': task.assigned_to.email if task.assigned_to else None,
                'due_date': task.due_date.isoformat()
            }
            for task in tasks[:20]  # Limit for performance
        ],
        'generated_at': report_data['generated_at']
    }


def generate_geotechnical_report(report_data):
    """Generate a geotechnical investigation report"""
    project = report_data['project']
    boreholes = report_data.get('boreholes', [])
    
    return {
        'title': f"Geotechnical Investigation Report - {project.project_code}",
        'project_info': {
            'name': project.name,
            'location': project.location_name,
            'client': project.client_name
        },
        'boreholes': [
            {
                'id': borehole.borehole_id,
                'depth': float(borehole.total_depth),
                'location': [borehole.location.x, borehole.location.y],
                'layers_count': borehole.layers.count(),
                'groundwater_level': float(borehole.groundwater_level) if borehole.groundwater_level else None
            }
            for borehole in boreholes
        ],
        'generated_at': report_data['generated_at']
    }


@shared_task
def sync_field_data():
    """
    Sync field data from mobile devices to central database
    """
    from apps.surveying.models import SurveyPoint
    
    try:
        # Find unsynced points
        unsynced_points = SurveyPoint.objects.filter(
            status='unconfirmed'
        ).select_related('project')
        
        logger.info(f"Found {unsynced_points.count()} unsynced survey points")
        
        for point in unsynced_points:
            # Process each point
            # Validate coordinates, run QC checks
            # Update status
            
            point.status = 'surveyed'
            point.save()
            
            logger.debug(f"Synced point {point.point_number} for project {point.project.project_code}")
        
        return {
            'status': 'success',
            'synced_count': unsynced_points.count()
        }
        
    except Exception as e:
        logger.error(f"Error syncing field data: {str(e)}")
        raise


@shared_task
def send_project_update_notifications():
    """
    Send daily project update notifications to stakeholders
    """
    from .models import Project
    
    today = timezone.now().date()
    week_from_now = today + timedelta(days=7)
    
    # Find projects with upcoming deadlines
    projects_with_deadlines = Project.objects.filter(
        estimated_end_date__lte=week_from_now,
        status__in=['active', 'on_hold']
    )
    
    for project in projects_with_deadlines:
        days_remaining = (project.estimated_end_date - today).days
        
        if days_remaining <= 7:
            # Send notification to project manager and team
            recipients = [project.project_manager.email] if project.project_manager else []
            recipients.extend(project.team_members.values_list('email', flat=True))
            
            if recipients:
                send_mail(
                    subject=f"Project Deadline Approaching: {project.project_code}",
                    message=f"Project {project.name} is due in {days_remaining} days.",
                    from_email='noreply@consultancy.com',
                    recipient_list=recipients
                )
                logger.info(f"Sent deadline notification for {project.project_code}")
    
    return {
        'status': 'success',
        'notifications_sent': len(projects_with_deadlines)
    }