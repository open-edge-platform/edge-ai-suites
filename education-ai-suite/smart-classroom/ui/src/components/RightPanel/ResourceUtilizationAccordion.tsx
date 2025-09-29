import React, { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import Accordion from '../common/Accordion'; 
import '../../assets/css/RightPanel.css'
import { useTranslation } from 'react-i18next';
import { useAppSelector } from '../../redux/hooks';

Chart.register(...registerables);

type GPUMetricKey = 'shared_memory_mb' | '3D_utilization_percent' | 'VideoDecode_utilization_percent' | 'VideoProcessing_utilization_percent' | 'Compute_utilization_percent';

interface GPUMetricConfig {
  index: number;
  color: string;
  label: string;
  yAxis: 'y';
  shortLabel: string;
}

type GPUMetricsConfig = Record<GPUMetricKey, GPUMetricConfig>;

const ResourceUtilizationAccordion: React.FC = () => {
  const { t } = useTranslation();
  
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const resourceMetrics = useAppSelector(s => s.resource?.metrics);
  const lastUpdated = useAppSelector(s => s.resource?.lastUpdated);
  
  const [resourceData, setResourceData] = useState<any>({
    cpu_utilization: [],
    gpu_utilization: [],
    memory: [],
    power: []
  });

  useEffect(() => {
    if (resourceMetrics && lastUpdated) {
      setResourceData(resourceMetrics);
    }
  }, [resourceMetrics, lastUpdated]);

  useEffect(() => {
    if (!sessionId) {
      console.log('No sessionId provided to ResourceUtilizationAccordion');
    } else {
      console.log('ResourceUtilizationAccordion sessionId:', sessionId);
    }
  }, [sessionId]);

  const gpuMetricsConfig: GPUMetricsConfig = {
    shared_memory_mb: { 
      index: 3, 
      color: 'rgba(255, 99, 132, 1)', 
      label: 'Shared Memory (GB)', 
      yAxis: 'y', 
      shortLabel: 'Shared Mem' 
    },
    '3D_utilization_percent': { 
      index: 4, 
      color: 'rgba(54, 162, 235, 1)', 
      label: '3D Utilization (%)', 
      yAxis: 'y', 
      shortLabel: '3D' 
    },
    VideoDecode_utilization_percent: { 
      index: 6, 
      color: 'rgba(255, 206, 86, 1)', 
      label: 'Video Decode (%)', 
      yAxis: 'y', 
      shortLabel: 'Vid Dec' 
    },
    VideoProcessing_utilization_percent: { 
      index: 7, 
      color: 'rgba(75, 192, 192, 1)', 
      label: 'Video Processing (%)', 
      yAxis: 'y', 
      shortLabel: 'Vid Proc' 
    },
    Compute_utilization_percent: { 
      index: 9, 
      color: 'rgba(153, 102, 255, 1)', 
      label: 'Compute Utilization (%)', 
      yAxis: 'y', 
      shortLabel: 'Compute' 
    },
  };

  const createChartData = (data: any[], metricConfigs: Record<string, GPUMetricConfig>) => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const labels = data.map((item: any) => item[0] ? new Date(item[0]).toLocaleTimeString() : '');

    const datasets = Object.entries(metricConfigs).map(([key, config]) => ({
      label: config.shortLabel,
      data: data.map((item: any) => {
        let value = item[config.index] || 0;
        if (key === 'shared_memory_mb') {
          value = value / 1024; // Convert MB to GB
        }
        return value;
      }),
      borderColor: config.color,
      backgroundColor: config.color.replace('1)', '0.2)'),
      fill: false,
      yAxisID: config.yAxis,
    }));

    return { labels, datasets };
  };

  const createSimpleChartData = (data: any[], label: string, color: string) => {
    if (!data || data.length === 0) return { labels: [], datasets: [] };

    const labels = data.map((item: any) => item[0] ? new Date(item[0]).toLocaleTimeString() : '');

    return {
      labels,
      datasets: [{
        label,
        data: data.map((item: any) => item[1] || 0),
        borderColor: color,
        backgroundColor: color.replace('1)', '0.2)'),
        fill: false,
      }]
    };
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        beginAtZero: true,
      },
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
      },
    },
  };

  const simpleChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: { y: { beginAtZero: true } },
    plugins: { legend: { display: true, position: 'top' as const } },
  };

  return (
    <Accordion title={t('accordion.resourceUtilization') || "Resource Utilization"}>
      <div className="accordion-subtitle">
        {t('accordion.subtitle_resource') || "System resource monitoring during AI processing"}
      </div>
      
      <div className="accordion-content">
        {sessionId ? (
          <>
            {/* CPU Utilization */}
            <div className="chart-section">
              <h4>{t('accordion.cpuUtilization') || "CPU Utilization"}</h4>
              <div style={{ height: '200px' }}>
                {resourceData.cpu_utilization && resourceData.cpu_utilization.length > 0 ? (
                  <Line 
                    data={createSimpleChartData(resourceData.cpu_utilization, 'CPU %', 'rgba(255, 99, 132, 1)')} 
                    options={simpleChartOptions} 
                  />
                ) : (
                  <p>{t('accordion.noData') || "No data available"}</p>
                )}
              </div>
            </div>

            {/* GPU Utilization */}
            <div className="chart-section">
              <h4>{t('accordion.gpuUtilization') || "GPU Utilization"}</h4>
              <div style={{ height: '200px' }}>
                {resourceData.gpu_utilization && resourceData.gpu_utilization.length > 0 ? (
                  <Line 
                    data={createChartData(resourceData.gpu_utilization, gpuMetricsConfig)} 
                    options={chartOptions} 
                  />
                ) : (
                  <p>{t('accordion.noData') || "No data available"}</p>
                )}
              </div>
            </div>

            {/* Memory Usage */}
            <div className="chart-section">
              <h4>{t('accordion.memoryUtilization') || "Memory Usage"}</h4>
              <div style={{ height: '200px' }}>
                {resourceData.memory && resourceData.memory.length > 0 ? (
                  <Line 
                    data={createSimpleChartData(resourceData.memory, 'Memory %', 'rgba(54, 162, 235, 1)')} 
                    options={simpleChartOptions} 
                  />
                ) : (
                  <p>{t('accordion.noData') || "No data available"}</p>
                )}
              </div>
            </div>

            {/* Power Consumption */}
            <div className="chart-section">
              <h4>{t('accordion.powerUtilization') || "Power Consumption"}</h4>
              <div style={{ height: '200px' }}>
                {resourceData.power && resourceData.power.length > 0 ? (
                  <Line 
                    data={createSimpleChartData(resourceData.power, 'Power (W)', 'rgba(75, 192, 192, 1)')} 
                    options={simpleChartOptions} 
                  />
                ) : (
                  <p>{t('accordion.noData') || "No data available"}</p>
                )}
              </div>
            </div>

            {lastUpdated && (
              <p className="last-updated">
                {t('accordion.lastUpdated') || "Last updated"}: {new Date(lastUpdated).toLocaleTimeString()}
              </p>
            )}
          </>
        ) : (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <p>{t('accordion.noSessionActive') || "No active session. Upload an audio file and start transcription to begin monitoring."}</p>
            <small style={{ color: '#666' }}>
              Session ID: {sessionId || 'Not set'}
            </small>
          </div>
        )}
      </div>
    </Accordion>
  );
};

export default ResourceUtilizationAccordion;
