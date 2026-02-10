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
      console.log('[ResourceUtilizationAccordion] Data updated:', {
        cpu: resourceMetrics.cpu_utilization?.length || 0,
        gpu: resourceMetrics.gpu_utilization?.length || 0,
        memory: resourceMetrics.memory?.length || 0,
        npu: resourceMetrics.npu_utilization?.length || 0,
      });
    }
  }, [resourceMetrics, lastUpdated]);

  const chartOptions = {
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
                <Line data={cpuChartData} options={chartOptions} />
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
                <Line data={memoryChartData} options={chartOptions} />
              ) : (
                <div className="no-data">Waiting for data...</div>
              )}
            </div>
          </div>

          {/* GPU Chart */}
          {resourceData.gpu_utilization.length > 0 && (
            <div className="graph-container">
              <h4>GPU Utilization</h4>
              <div style={{ height: '200px' }}>
                <Line data={gpuChartData} options={chartOptions} />
              </div>
            </div>
          )}

          {/* NPU Chart */}
          {resourceData.npu_utilization.length > 0 && (
            <div className="graph-container">
              <h4>NPU Utilization</h4>
              <div style={{ height: '200px' }}>
                <Line data={npuChartData} options={chartOptions} />
              </div>
            </div>
          )}
        </div>
      </div>
    </Accordion>
  );
}

export default ResourceUtilizationAccordion;
