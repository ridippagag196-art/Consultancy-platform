import axios from 'axios';
import { storage } from '../utils/storage';
import { Project, ProjectTask, ProjectPhase } from '../types';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class ProjectService {
  private getHeaders() {
    const token = storage.get('auth_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    };
  }

  async getAllProjects(params?: any): Promise<Project[]> {
    const response = await axios.get(`${API_URL}/projects/`, {
      headers: this.getHeaders(),
      params,
    });
    return response.data;
  }

  async getProject(id: string): Promise<Project> {
    const response = await axios.get(`${API_URL}/projects/${id}/`, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async createProject(data: Partial<Project>): Promise<Project> {
    const response = await axios.post(`${API_URL}/projects/`, data, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async updateProject(id: string, data: Partial<Project>): Promise<Project> {
    const response = await axios.put(`${API_URL}/projects/${id}/`, data, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async deleteProject(id: string): Promise<void> {
    await axios.delete(`${API_URL}/projects/${id}/`, {
      headers: this.getHeaders(),
    });
  }

  async getTasks(projectId?: string): Promise<ProjectTask[]> {
    const url = projectId 
      ? `${API_URL}/projects/${projectId}/tasks/`
      : `${API_URL}/tasks/`;
    const response = await axios.get(url, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async createTask(projectId: string, data: Partial<ProjectTask>): Promise<ProjectTask> {
    const response = await axios.post(
      `${API_URL}/projects/${projectId}/tasks/`,
      data,
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  async updateTask(taskId: string, data: Partial<ProjectTask>): Promise<ProjectTask> {
    const response = await axios.put(`${API_URL}/tasks/${taskId}/`, data, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async deleteTask(taskId: string): Promise<void> {
    await axios.delete(`${API_URL}/tasks/${taskId}/`, {
      headers: this.getHeaders(),
    });
  }

  async getPhases(projectId: string): Promise<ProjectPhase[]> {
    const response = await axios.get(`${API_URL}/projects/${projectId}/phases/`, {
      headers: this.getHeaders(),
    });
    return response.data;
  }

  async assignTeamMember(projectId: string, userId: string): Promise<void> {
    await axios.post(
      `${API_URL}/projects/${projectId}/assign_team_member/`,
      { user_id: userId },
      { headers: this.getHeaders() }
    );
  }

  async removeTeamMember(projectId: string, userId: string): Promise<void> {
    await axios.post(
      `${API_URL}/projects/${projectId}/remove_team_member/`,
      { user_id: userId },
      { headers: this.getHeaders() }
    );
  }

  async getAnalytics(projectId: string): Promise<any> {
    const response = await axios.get(
      `${API_URL}/projects/${projectId}/analytics/`,
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  async generateReport(projectId: string, reportType: string = 'summary'): Promise<{ task_id: string }> {
    const response = await axios.post(
      `${API_URL}/projects/${projectId}/generate_report/`,
      { report_type: reportType },
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  async cloneProject(projectId: string): Promise<{ new_project_id: string, new_project_code: string }> {
    const response = await axios.post(
      `${API_URL}/projects/${projectId}/clone_project/`,
      {},
      { headers: this.getHeaders() }
    );
    return response.data;
  }

  // Helper methods
  getProjectStatusColor(status: string): string {
    const colors = {
      draft: '#bdbdbd',
      active: '#1976d2',
      on_hold: '#ed6c02',
      completed: '#2e7d32',
      cancelled: '#d32f2f',
      archived: '#757575',
    };
    return colors[status as keyof typeof colors] || '#bdbdbd';
  }

  getTaskPriorityColor(priority: string): string {
    const colors = {
      low: '#4caf50',
      medium: '#ff9800',
      high: '#f44336',
      urgent: '#d32f2f',
    };
    return colors[priority as keyof typeof colors] || '#4caf50';
  }

  calculateProgress(tasks: ProjectTask[]): number {
    if (tasks.length === 0) return 0;
    const completed = tasks.filter(t => t.status === 'completed').length;
    return (completed / tasks.length) * 100;
  }

  calculateBudgetVariance(estimated: number, actual: number): number {
    if (estimated === 0) return 0;
    return ((actual - estimated) / estimated) * 100;
  }
}

export const projectService = new ProjectService();