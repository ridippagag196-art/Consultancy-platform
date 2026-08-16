import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  Modal,
  Alert,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
} from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';
import { useNavigation } from '@react-navigation/native';
import { useDispatch, useSelector } from 'react-redux';
import { MaterialIcons, FontAwesome5 } from '@expo/vector-icons';
import * as Location from 'expo-location';
import RNFS from 'react-native-fs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { surveyService } from '../services/surveyService';
import { pointsActions } from '../store/slices/pointsSlice';
import { Button, Card, Input, PhotoCapture } from '../components/common';
import { theme } from '../theme';
import { useAuth } from '../contexts/AuthContext';

const { width, height } = Dimensions.get('window');

export const SurveyScreen = ({ route }) => {
  const navigation = useNavigation();
  const dispatch = useDispatch();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  
  const { projectId } = route.params || {};
  const [selectedPoint, setSelectedPoint] = useState(null);
  const [showPointModal, setShowPointModal] = useState(false);
  const [isCollecting, setIsCollecting] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [points, setPoints] = useState([]);
  const mapRef = useRef(null);
  
  // Fetch survey points
  const { data: surveyPoints, isLoading, refetch } = useQuery(
    ['surveyPoints', projectId],
    () => surveyService.getPoints(projectId),
    {
      enabled: !!projectId,
      onSuccess: (data) => {
        setPoints(data);
        dispatch(pointsActions.setPoints(data));
      }
    }
  );
  
  // Add point mutation
  const addPointMutation = useMutation(
    (pointData) => surveyService.addPoint(pointData),
    {
      onSuccess: (newPoint) => {
        setPoints(prev => [...prev, newPoint]);
        queryClient.invalidateQueries(['surveyPoints', projectId]);
        Alert.alert('Success', 'Survey point added successfully');
      },
      onError: (error) => {
        Alert.alert('Error', 'Failed to add survey point');
        console.error(error);
      }
    }
  );
  
  // Get current location
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location access is required for surveying');
        return;
      }
      
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      
      setCurrentLocation({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy: location.coords.accuracy,
      });
    })();
  }, []);
  
  // Watch location for GNSS data
  useEffect(() => {
    let locationSubscription;
    
    if (isCollecting) {
      locationSubscription = Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Highest,
          timeInterval: 1000,
          distanceInterval: 1,
        },
        (location) => {
          setCurrentLocation({
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
            accuracy: location.coords.accuracy,
            altitude: location.coords.altitude,
            speed: location.coords.speed,
          });
        }
      );
    }
    
    return () => {
      if (locationSubscription) {
        locationSubscription.remove();
      }
    };
  }, [isCollecting]);
  
  const handleCollectPoint = async (pointType) => {
    if (!currentLocation) {
      Alert.alert('Error', 'No GPS signal available');
      return;
    }
    
    setIsCollecting(false);
    
    const pointData = {
      project: projectId,
      point_number: `P-${Date.now()}`,
      point_type: pointType,
      latitude: currentLocation.latitude,
      longitude: currentLocation.longitude,
      elevation: currentLocation.altitude,
      accuracy_h: currentLocation.accuracy,
      status: 'unconfirmed',
      surveyor: user.id,
      survey_date: new Date().toISOString().split('T')[0],
      field_notes: '',
    };
    
    addPointMutation.mutate(pointData);
  };
  
  const handleExportData = async () => {
    try {
      const csvData = surveyService.exportToCSV(points);
      const filePath = `${RNFS.DocumentDirectoryPath}/survey_data_${Date.now()}.csv`;
      await RNFS.writeFile(filePath, csvData, 'utf8');
      
      Alert.alert(
        'Export Successful',
        `Data exported to ${filePath}`,
        [{ text: 'OK' }]
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to export survey data');
      console.error(error);
    }
  };
  
  const renderPointItem = ({ item }) => (
    <TouchableOpacity
      style={styles.pointItem}
      onPress={() => {
        setSelectedPoint(item);
        setShowPointModal(true);
      }}
    >
      <View style={styles.pointInfo}>
        <Text style={styles.pointNumber}>{item.point_number}</Text>
        <Text style={styles.pointType}>{item.point_type}</Text>
        <Text style={styles.pointCoordinates}>
          {item.latitude.toFixed(6)}, {item.longitude.toFixed(6)}
        </Text>
      </View>
      <View style={styles.pointStatus}>
        <View
          style={[
            styles.statusDot,
            { backgroundColor: item.status === 'surveyed' ? '#4CAF50' : '#FFC107' }
          ]}
        />
        <Text style={styles.statusText}>{item.status}</Text>
      </View>
    </TouchableOpacity>
  );
  
  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };
  
  return (
    <View style={styles.container}>
      {/* Map View */}
      <View style={styles.mapContainer}>
        <MapView
          ref={mapRef}
          style={styles.map}
          initialRegion={{
            latitude: currentLocation?.latitude || -34.6037,
            longitude: currentLocation?.longitude || -58.3816,
            latitudeDelta: 0.01,
            longitudeDelta: 0.01,
          }}
          showsUserLocation={true}
          showsMyLocationButton={true}
        >
          {points.map((point) => (
            <Marker
              key={point.id}
              coordinate={{
                latitude: point.latitude,
                longitude: point.longitude,
              }}
              title={point.point_number}
              description={point.point_type}
              pinColor={point.status === 'surveyed' ? '#4CAF50' : '#FFC107'}
              onPress={() => {
                setSelectedPoint(point);
                setShowPointModal(true);
              }}
            />
          ))}
        </MapView>
        
        {/* Collection Button */}
        {!isCollecting ? (
          <TouchableOpacity
            style={styles.collectButton}
            onPress={() => setIsCollecting(true)}
          >
            <MaterialIcons name="gps-fixed" size={24} color="#fff" />
            <Text style={styles.collectButtonText}>Collect Point</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.collectingContainer}>
            <View style={styles.collectingInfo}>
              <MaterialIcons name="gps-active" size={20} color="#fff" />
              <Text style={styles.collectingText}>
                Collecting GPS Data...
              </Text>
            </View>
            <FlatList
              data={[
                { key: 'gcn', label: 'GCN Point' },
                { key: 'boundary', label: 'Boundary' },
                { key: 'topographic', label: 'Topographic' },
                { key: 'feature', label: 'Feature' },
                { key: 'building', label: 'Building' },
                { key: 'utility', label: 'Utility' },
              ]}
              horizontal
              showsHorizontalScrollIndicator={false}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={styles.pointTypeButton}
                  onPress={() => handleCollectPoint(item.key)}
                >
                  <Text style={styles.pointTypeButtonText}>{item.label}</Text>
                </TouchableOpacity>
              )}
              keyExtractor={item => item.key}
              style={styles.pointTypesList}
            />
          </View>
        )}
      </View>
      
      {/* Points List */}
      <View style={styles.pointsList}>
        <View style={styles.listHeader}>
          <Text style={styles.listTitle}>
            Survey Points ({points.length})
          </Text>
          <View style={styles.listActions}>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={handleExportData}
            >
              <FontAwesome5 name="file-export" size={16} color={theme.colors.primary} />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={onRefresh}
            >
              <MaterialIcons name="refresh" size={20} color={theme.colors.primary} />
            </TouchableOpacity>
          </View>
        </View>
        
        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={theme.colors.primary} />
          </View>
        ) : (
          <FlatList
            data={points}
            renderItem={renderPointItem}
            keyExtractor={(item) => item.id}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
            }
            contentContainerStyle={styles.pointsListContent}
          />
        )}
      </View>
      
      {/* Point Detail Modal */}
      <Modal
        visible={showPointModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowPointModal(false)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            {selectedPoint && (
              <>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>
                    Point {selectedPoint.point_number}
                  </Text>
                  <TouchableOpacity
                    onPress={() => setShowPointModal(false)}
                  >
                    <MaterialIcons name="close" size={24} color="#333" />
                  </TouchableOpacity>
                </View>
                
                <View style={styles.modalBody}>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Type:</Text>
                    <Text style={styles.modalValue}>{selectedPoint.point_type}</Text>
                  </View>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Coordinates:</Text>
                    <Text style={styles.modalValue}>
                      {selectedPoint.latitude.toFixed(6)}, {selectedPoint.longitude.toFixed(6)}
                    </Text>
                  </View>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Elevation:</Text>
                    <Text style={styles.modalValue}>
                      {selectedPoint.elevation ? `${selectedPoint.elevation.toFixed(3)}m` : 'N/A'}
                    </Text>
                  </View>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Accuracy:</Text>
                    <Text style={styles.modalValue}>
                      {selectedPoint.accuracy_h ? `${selectedPoint.accuracy_h.toFixed(3)}m` : 'N/A'}
                    </Text>
                  </View>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Status:</Text>
                    <Text style={[
                      styles.modalValue,
                      { color: selectedPoint.status === 'surveyed' ? '#4CAF50' : '#FFC107' }
                    ]}>
                      {selectedPoint.status}
                    </Text>
                  </View>
                  <View style={styles.modalRow}>
                    <Text style={styles.modalLabel}>Survey Date:</Text>
                    <Text style={styles.modalValue}>{selectedPoint.survey_date}</Text>
                  </View>
                  
                  {selectedPoint.field_notes && (
                    <View style={styles.modalRow}>
                      <Text style={styles.modalLabel}>Notes:</Text>
                      <Text style={styles.modalValue}>{selectedPoint.field_notes}</Text>
                    </View>
                  )}
                </View>
                
                <View style={styles.modalActions}>
                  <Button
                    title="Edit"
                    onPress={() => {
                      setShowPointModal(false);
                      navigation.navigate('EditPoint', { pointId: selectedPoint.id });
                    }}
                    style={styles.modalButton}
                  />
                  <Button
                    title="Delete"
                    variant="danger"
                    onPress={() => {
                      Alert.alert(
                        'Delete Point',
                        'Are you sure you want to delete this point?',
                        [
                          { text: 'Cancel', style: 'cancel' },
                          {
                            text: 'Delete',
                            style: 'destructive',
                            onPress: async () => {
                              await surveyService.deletePoint(selectedPoint.id);
                              setPoints(prev => prev.filter(p => p.id !== selectedPoint.id));
                              setShowPointModal(false);
                              queryClient.invalidateQueries(['surveyPoints', projectId]);
                            }
                          }
                        ]
                      );
                    }}
                    style={[styles.modalButton, styles.deleteButton]}
                  />
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  mapContainer: {
    height: height * 0.5,
    position: 'relative',
  },
  map: {
    ...StyleSheet.absoluteFillObject,
  },
  collectButton: {
    position: 'absolute',
    bottom: 20,
    alignSelf: 'center',
    backgroundColor: theme.colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 25,
    flexDirection: 'row',
    alignItems: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  collectButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
    marginLeft: 8,
  },
  collectingContainer: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: 'rgba(0,0,0,0.8)',
    borderRadius: 12,
    padding: 16,
  },
  collectingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  collectingText: {
    color: '#fff',
    fontSize: 14,
    marginLeft: 8,
  },
  pointTypesList: {
    maxHeight: 50,
  },
  pointTypeButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 8,
  },
  pointTypeButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '500',
  },
  pointsList: {
    flex: 1,
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    marginTop: -20,
  },
  listHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  listActions: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    padding: 8,
  },
  pointsListContent: {
    padding: 16,
  },
  pointItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  pointInfo: {
    flex: 1,
  },
  pointNumber: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  pointType: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  pointCoordinates: {
    fontSize: 11,
    color: '#999',
    marginTop: 2,
  },
  pointStatus: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 4,
  },
  statusText: {
    fontSize: 12,
    color: '#666',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  modalContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 24,
    width: '90%',
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  modalBody: {
    marginBottom: 16,
  },
  modalRow: {
    flexDirection: 'row',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  modalLabel: {
    width: 100,
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  modalValue: {
    flex: 1,
    fontSize: 14,
    color: '#333',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  modalButton: {
    flex: 1,
  },
  deleteButton: {
    backgroundColor: '#f44336',
  },
});