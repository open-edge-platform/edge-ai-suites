import React, { useEffect, useState } from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import '../../assets/css/RightPanel.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export function ResourceUtilizationAccordion() {
  const resourceMetrics = useAppSelector((state) => state.metrics.resources);
  const lastUpdated = useAppSelector((state) => state.metrics.lastUpdated);
  
  const [resourceData, setResourceData] = useState<any>({
    cpu_utilization: [],
    gpu_utilization: [],
    memory: [],
    power: [],
    npu_utilization: []
  });

  useEffect(() => {
    if (resourceMetrics && lastUpdated) {
      setResourceData(resourceMetrics);
    }
  }, [resourceMetrics, lastUpdated]);

  const baseChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        title: {
          display: true,
          text: 'Utilization (%)',
        },
      },
      x: {
        display: true,
        ticks: {
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10,
        },
      },
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
      },
    },
  };

  // Auto-scale Y-axis for memory & GPU so small fluctuations are visible
  const autoScaleChartOptions = {
    ...baseChartOptions,
    scales: {
      ...baseChartOptions.scales,
      y: {
        ...baseChartOptions.scales.y,
        max: undefined as number | undefined,
        suggestedMax: 100,
      },
    },
  };

  // Helper to format timestamps
  const formatTimestamp = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString();
    } catch {
      return ts;
    }
  };

  // CPU Chart
  const cpuChartData = {
    labels: resourceData.cpu_utilization.map((item: any) => formatTimestamp(item[0])),
    datasets: [{
      label: 'CPU %',
      data: resourceData.cpu_utilization.map((item: any) => item[1]),
      borderColor: 'rgb(54, 162, 235)',
      backgroundColor: 'rgba(54, 162, 235, 0.5)',
      tension: 0.4,
    }],
  };

  // GPU Chart (take first GPU value if multiple)
  const gpuChartData = {
    labels: resourceData.gpu_utilization.map((item: any) => formatTimestamp(item[0])),
    datasets: [{
      label: 'GPU %',
      data: resourceData.gpu_utilization.map((item: any) => item[1] || 0),
      borderColor: 'rgb(75, 192, 192)',
      backgroundColor: 'rgba(75, 192, 192, 0.5)',
      tension: 0.4,
    }],
  };

  // Memory Chart (use percentage which is item[4])
  const memoryChartData = {
    labels: resourceData.memory.map((item: any) => formatTimestamp(item[0])),
    datasets: [{
      label: 'Memory %',
      data: resourceData.memory.map((item: any) => item[4] || 0),
      borderColor: 'rgb(255, 99, 132)',
      backgroundColor: 'rgba(255, 99, 132, 0.5)',
      tension: 0.4,
    }],
  };

  // NPU Chart
  const npuChartData = {
    labels: resourceData.npu_utilization.map((item: any) => formatTimestamp(item[0])),
    datasets: [{
      label: 'NPU %',
      data: resourceData.npu_utilization.map((item: any) => item[1] || 0),
      borderColor: 'rgb(153, 102, 255)',
      backgroundColor: 'rgba(153, 102, 255, 0.5)',
      tension: 0.4,
    }],
  };

  return (
    <Accordion title="Resource Utilization" defaultOpen>
      <div className="resource-utilization-content">
        {lastUpdated && (
          <p className="last-updated">
            Last updated: {new Date(lastUpdated).toLocaleTimeString()}
          </p>
        )}

        <div className="metrics-graphs">
          {/* CPU Chart */}
          <div className="graph-container">
            <h4>CPU Utilization</h4>
            <div style={{ height: '200px' }}>
              {resourceData.cpu_utilization.length > 0 ? (
                <Line data={cpuChartData} options={baseChartOptions} />
              ) : (
                <div className="no-data">Waiting for data...</div>
              )}
            </div>
          </div>

          {/* Memory Chart */}
          <div className="graph-container">
            <h4>Memory Utilization</h4>
            <div style={{ height: '200px' }}>
              {resourceData.memory.length > 0 ? (
                <Line data={memoryChartData} options={autoScaleChartOptions} />
              ) : (
                <div className="no-data">Waiting for data...</div>
              )}
            </div>
          </div>

          {/* GPU Chart */}
          <div className="graph-container">
            <h4>GPU Utilization</h4>
            <div style={{ height: '200px' }}>
              {resourceData.gpu_utilization.length > 0 ? (
                <Line data={gpuChartData} options={autoScaleChartOptions} />
              ) : (
                <div className="no-data">Waiting for data...</div>
              )}
            </div>
          </div>

          {/* NPU Chart */}
          <div className="graph-container">
            <h4>NPU Utilization</h4>
            <div style={{ height: '200px' }}>
              {resourceData.npu_utilization.length > 0 ? (
                <Line data={npuChartData} options={baseChartOptions} />
              ) : (
                <div className="no-data">Waiting for data...</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Accordion>
  );
}

export default ResourceUtilizationAccordion;
