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
    power: []
  });

  useEffect(() => {
    if (resourceMetrics && lastUpdated) {
      setResourceData(resourceMetrics);
    }
  }, [resourceMetrics, lastUpdated]);

  const createSimpleChartData = (data: number[], label: string, color: string) => ({
    labels: data.map((_, i) => `${i}`),
    datasets: [
      {
        label,
        data,
        borderColor: color,
        backgroundColor: color.replace('1)', '0.2)'),
        tension: 0.4,
        fill: true
      }
    ]
  });

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        beginAtZero: true,
        max: 100
      }
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const
      }
    }
  };

  return (
    <Accordion title="Resource Utilization">
      <div className="accordion-subtitle">
        System Resource Monitoring
      </div>

      <div className="charts-container">
        {/* CPU Utilization */}
        <div className="chart-section">
          <h4>CPU Utilization (%)</h4>
          <div style={{ height: '200px' }}>
            {resourceData.cpu_utilization.length > 0 ? (
              <Line
                data={createSimpleChartData(
                  resourceData.cpu_utilization,
                  'CPU Usage',
                  'rgba(54, 162, 235, 1)'
                )}
                options={chartOptions}
              />
            ) : (
              <p>No data available</p>
            )}
          </div>
        </div>

        {/* Memory Usage */}
        <div className="chart-section">
          <h4>Memory Usage (%)</h4>
          <div style={{ height: '200px' }}>
            {resourceData.memory.length > 0 ? (
              <Line
                data={createSimpleChartData(
                  resourceData.memory,
                  'Memory',
                  'rgba(255, 99, 132, 1)'
                )}
                options={chartOptions}
              />
            ) : (
              <p>No data available</p>
            )}
          </div>
        </div>

        {/* Power Consumption */}
        {resourceData.power.length > 0 && (
          <div className="chart-section">
            <h4>Power (W)</h4>
            <div style={{ height: '200px' }}>
              <Line
                data={createSimpleChartData(
                  resourceData.power,
                  'Power',
                  'rgba(75, 192, 192, 1)'
                )}
                options={{
                  ...chartOptions,
                  scales: { y: { beginAtZero: true } }
                }}
              />
            </div>
          </div>
        )}
      </div>
    </Accordion>
  );
}

export default ResourceUtilizationAccordion;