import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  IconButton,
  Button,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Divider,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Business,
  People,
  Description,
  AttachMoney,
  MoreVert,
  Refresh,
  ArrowForward,
} from '@mui/icons-material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Line, Pie, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { format, formatDistanceToNow } from 'date-fns';

import { projectService } from '../services/projectService';
import { surveyService } from '../services/surveyService';
import { geotechnicalService } from '../services/geotechnicalService';
import { useAuth } from '../hooks/useAuth';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

interface DashboardStats {
  totalProjects: number;
  activeProjects: number;
  completedProjects: number;
  totalRevenue: number;
  revenueGrowth: number;
  teamMembers: number;
  pendingTasks: number;
  upcomingDeadlines: number;
}

interface RecentActivity {
  id: string;
  type: 'project' | 'survey' | 'report' | 'geotechnical';
  description: string;
  timestamp: Date;
  user: string;
}

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentActivities, setRecentActivities] = useState<RecentActivity[]>([]);
  
  // Fetch dashboard data
  const { data, isLoading, refetch } = useQuery(
    ['dashboard'],
    async () => {
      const [projects, tasks, team] = await Promise.all([
        projectService.getAllProjects(),
        projectService.getTasks(),
        projectService.getTeamMembers(),
      ]);
      
      return { projects, tasks, team };
    },
    {
      onSuccess: (data) => {
        // Calculate stats
        const totalProjects = data.projects.length;
        const activeProjects = data.projects.filter(p => p.status === 'active').length;
        const completedProjects = data.projects.filter(p => p.status === 'completed').length;
        
        const totalRevenue = data.projects.reduce((sum, p) => sum + p.actual_cost, 0);
        const lastMonthRevenue = data.projects
          .filter(p => new Date(p.created_at) > new Date(Date.now() - 30 * 24 * 60 * 60 * 1000))
          .reduce((sum, p) => sum + p.actual_cost, 0);
        
        const pendingTasks = data.tasks.filter(t => t.status !== 'completed').length;
        const upcomingDeadlines = data.tasks.filter(
          t => new Date(t.due_date) < new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) && t.status !== 'completed'
        ).length;
        
        setStats({
          totalProjects,
          activeProjects,
          completedProjects,
          totalRevenue,
          revenueGrowth: lastMonthRevenue > 0 ? ((totalRevenue - lastMonthRevenue) / lastMonthRevenue) * 100 : 0,
          teamMembers: data.team.length,
          pendingTasks,
          upcomingDeadlines,
        });
        
        // Generate recent activities
        const activities: RecentActivity[] = [
          ...data.projects.slice(0, 3).map(p => ({
            id: p.id,
            type: 'project' as const,
            description: `Project "${p.name}" ${p.status === 'completed' ? 'completed' : 'updated'}`,
            timestamp: new Date(p.updated_at),
            user: p.project_manager?.name || 'System',
          })),
          ...data.tasks.slice(0, 3).map(t => ({
            id: t.id,
            type: 'survey' as const,
            description: `Task "${t.title}" ${t.status === 'completed' ? 'completed' : 'in progress'}`,
            timestamp: new Date(t.updated_at),
            user: t.assigned_to?.name || 'Unassigned',
          })),
        ].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
         .slice(0, 10);
        
        setRecentActivities(activities);
      }
    }
  );
  
  // Project data for charts
  const projectChartData = {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    datasets: [
      {
        label: 'Projects Started',
        data: [5, 7, 4, 8, 6, 9, 7, 10, 8, 6, 5, 8],
        borderColor: '#1976d2',
        backgroundColor: 'rgba(25, 118, 210, 0.1)',
        tension: 0.4,
      },
      {
        label: 'Revenue',
        data: [45000, 52000, 48000, 67000, 59000, 72000, 68000, 85000, 78000, 69000, 62000, 91000],
        borderColor: '#2e7d32',
        backgroundColor: 'rgba(46, 125, 50, 0.1)',
        tension: 0.4,
      },
    ],
  };
  
  // Project type distribution
  const projectTypeData = {
    labels: ['Consultancy', 'Surveying', 'Geotechnical', 'Design', 'BIM', 'Construction'],
    datasets: [
      {
        data: [12, 19, 8, 15, 6, 10],
        backgroundColor: [
          '#1976d2',
          '#2e7d32',
          '#ed6c02',
          '#9c27b0',
          '#d32f2f',
          '#0288d1',
        ],
      },
    ],
  };
  
  const handleRefresh = () => {
    queryClient.invalidateQueries(['dashboard']);
    refetch();
  };
  
  const StatCard: React.FC<{
    title: string;
    value: number | string;
    subtitle?: string;
    icon: React.ReactNode;
    color: string;
    trend?: number;
    loading: boolean;
  }> = ({ title, value, subtitle, icon, color, trend, loading }) => (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box>
            <Typography variant="body2" color="textSecondary">
              {title}
            </Typography>
            <Typography variant="h4" component="div" gutterBottom>
              {loading ? '...' : value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="textSecondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Avatar sx={{ bgcolor: color }}>
            {icon}
          </Avatar>
        </Box>
        {trend !== undefined && (
          <Box display="flex" alignItems="center" mt={1}>
            {trend > 0 ? (
              <TrendingUp sx={{ color: '#2e7d32', fontSize: 16 }} />
            ) : (
              <TrendingDown sx={{ color: '#d32f2f', fontSize: 16 }} />
            )}
            <Typography
              variant="caption"
              sx={{
                color: trend > 0 ? '#2e7d32' : '#d32f2f',
                fontWeight: 'bold',
                ml: 0.5,
              }}
            >
              {Math.abs(trend).toFixed(1)}%
            </Typography>
            <Typography variant="caption" color="textSecondary" ml={1}>
              vs last month
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
  
  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Welcome back, {user?.name || 'User'}
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Here's what's happening with your consultancy projects
          </Typography>
        </Box>
        <Box display="flex" gap={2}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={handleRefresh}
            disabled={isLoading}
          >
            Refresh
          </Button>
          <Button variant="contained" component="a" href="/projects/new">
            New Project
          </Button>
        </Box>
      </Box>
      
      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Projects"
            value={stats?.totalProjects || 0}
            icon={<Business />}
            color="#1976d2"
            loading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Active Projects"
            value={stats?.activeProjects || 0}
            subtitle={`${stats?.completedProjects || 0} completed`}
            icon={<Description />}
            color="#2e7d32"
            loading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Revenue"
            value={`$${(stats?.totalRevenue || 0).toLocaleString()}`}
            icon={<AttachMoney />}
            color="#ed6c02"
            trend={stats?.revenueGrowth}
            loading={isLoading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Team Members"
            value={stats?.teamMembers || 0}
            subtitle={`${stats?.pendingTasks || 0} tasks pending`}
            icon={<People />}
            color="#9c27b0"
            loading={isLoading}
          />
        </Grid>
      </Grid>
      
      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">Project & Revenue Trends</Typography>
              <IconButton size="small">
                <MoreVert />
              </IconButton>
            </Box>
            <Line
              data={projectChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    position: 'top',
                  },
                },
                scales: {
                  y: {
                    beginAtZero: true,
                  },
                },
              }}
              height={250}
            />
          </Paper>
        </Grid>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Project Distribution
            </Typography>
            <Pie
              data={projectTypeData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    position: 'bottom',
                  },
                },
              }}
              height={250}
            />
          </Paper>
        </Grid>
      </Grid>
      
      {/* Recent Activity & Quick Actions */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">Recent Activity</Typography>
              <Button
                size="small"
                endIcon={<ArrowForward />}
                component="a"
                href="/activities"
              >
                View All
              </Button>
            </Box>
            <List>
              {recentActivities.map((activity, index) => (
                <React.Fragment key={activity.id}>
                  <ListItem
                    button
                    onClick={() => {
                      // Navigate to relevant page
                    }}
                  >
                    <ListItemAvatar>
                      <Avatar sx={{ bgcolor: 'primary.light' }}>
                        {activity.type === 'project' && <Business />}
                        {activity.type === 'survey' && <Description />}
                        {activity.type === 'geotechnical' && <Business />}
                        {activity.type === 'report' && <Description />}
                      </Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={activity.description}
                      secondary={
                        <Box component="span" display="flex" alignItems="center" gap={1}>
                          <Typography variant="caption" color="textSecondary">
                            {activity.user}
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            •
                          </Typography>
                          <Typography variant="caption" color="textSecondary">
                            {formatDistanceToNow(activity.timestamp, { addSuffix: true })}
                          </Typography>
                        </Box>
                      }
                    />
                    <Chip
                      label={activity.type}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </ListItem>
                  {index < recentActivities.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Box display="flex" flexDirection="column" gap={2}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Description />}
                component="a"
                href="/survey/new"
              >
                New Survey
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Business />}
                component="a"
                href="/geotechnical/new"
              >
                New Borehole
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<AttachMoney />}
                component="a"
                href="/invoices/new"
              >
                Generate Invoice
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<People />}
                component="a"
                href="/team"
              >
                Manage Team
              </Button>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<Description />}
                component="a"
                href="/reports"
              >
                Generate Report
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};