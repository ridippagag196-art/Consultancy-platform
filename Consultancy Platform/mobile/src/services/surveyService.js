import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import * as FileSystem from 'expo-file-system';
import { Buffer } from 'buffer';

const API_URL = process.env.API_URL || 'http://localhost:8000/api';

class SurveyService {
  constructor() {
    this.baseURL = API_URL;
    this.token = null;
  }

  async getToken() {
    if (!this.token) {
      this.token = await AsyncStorage.getItem('auth_token');
    }
    return this.token;
  }

  async request(config) {
    const token = await this.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...config.headers,
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await axios({
        ...config,
        baseURL: this.baseURL,
        headers,
      });
      return response.data;
    } catch (error) {
      console.error('API Request Error:', error);
      throw error;
    }
  }

  async getPoints(projectId) {
    return this.request({
      method: 'GET',
      url: `/projects/${projectId}/survey-points/`,
    });
  }

  async addPoint(pointData) {
    return this.request({
      method: 'POST',
      url: '/survey-points/',
      data: pointData,
    });
  }

  async updatePoint(pointId, pointData) {
    return this.request({
      method: 'PUT',
      url: `/survey-points/${pointId}/`,
      data: pointData,
    });
  }

  async deletePoint(pointId) {
    return this.request({
      method: 'DELETE',
      url: `/survey-points/${pointId}/`,
    });
  }

  async uploadPhotos(pointId, photos) {
    const formData = new FormData();
    
    photos.forEach((photo, index) => {
      formData.append(`photo_${index}`, {
        uri: photo.uri,
        type: 'image/jpeg',
        name: `photo_${index}_${Date.now()}.jpg`,
      });
    });

    return this.request({
      method: 'POST',
      url: `/survey-points/${pointId}/upload-photos/`,
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }

  exportToCSV(points) {
    if (!points || points.length === 0) return '';
    
    // Define CSV headers
    const headers = [
      'Point Number',
      'Type',
      'Latitude',
      'Longitude',
      'Elevation',
      'Accuracy',
      'Status',
      'Survey Date',
      'Notes'
    ];
    
    // Create CSV rows
    const rows = points.map(point => [
      point.point_number,
      point.point_type,
      point.latitude.toFixed(8),
      point.longitude.toFixed(8),
      point.elevation ? point.elevation.toFixed(3) : '',
      point.accuracy_h ? point.accuracy_h.toFixed(3) : '',
      point.status,
      point.survey_date,
      point.field_notes || ''
    ]);
    
    // Combine headers and rows
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    return csvContent;
  }

  async exportToShapefile(points) {
    // This would require a GIS library like shapefile-js
    // For now, we'll return a GeoJSON
    const geojson = {
      type: 'FeatureCollection',
      features: points.map(point => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [point.longitude, point.latitude]
        },
        properties: {
          point_number: point.point_number,
          point_type: point.point_type,
          elevation: point.elevation,
          status: point.status,
          survey_date: point.survey_date,
          notes: point.field_notes || ''
        }
      }))
    };
    
    return geojson;
  }

  async syncOfflineData() {
    try {
      // Get offline points from local storage
      const offlineData = await AsyncStorage.getItem('offline_survey_points');
      if (!offlineData) return [];
      
      const offlinePoints = JSON.parse(offlineData);
      const syncedPoints = [];
      
      for (const point of offlinePoints) {
        try {
          // Try to sync each point
          const result = await this.addPoint(point);
          syncedPoints.push(result);
          
          // Remove from offline storage
          const remainingPoints = offlinePoints.filter(p => p.id !== point.id);
          await AsyncStorage.setItem('offline_survey_points', JSON.stringify(remainingPoints));
        } catch (error) {
          console.error('Failed to sync point:', point.id, error);
        }
      }
      
      return syncedPoints;
    } catch (error) {
      console.error('Error syncing offline data:', error);
      throw error;
    }
  }

  async saveOfflinePoint(point) {
    try {
      const offlineData = await AsyncStorage.getItem('offline_survey_points');
      const offlinePoints = offlineData ? JSON.parse(offlineData) : [];
      
      // Add offline flag to point
      const offlinePoint = {
        ...point,
        offline: true,
        offline_id: `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      };
      
      offlinePoints.push(offlinePoint);
      await AsyncStorage.setItem('offline_survey_points', JSON.stringify(offlinePoints));
      
      return offlinePoint;
    } catch (error) {
      console.error('Error saving offline point:', error);
      throw error;
    }
  }
}

export const surveyService = new SurveyService();