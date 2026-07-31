import React from 'react';
import { useAppSelector } from '../../redux/hooks';
import Accordion from '../common/Accordion';
import '../../assets/css/RightPanel.css';

/**
 * Strip noisy hardware-probe artifacts from platform strings before display:
 *   - PCI bus/class prefix, e.g. "0b.0 Processing accelerators [1200]:"
 *   - PCI vendor:device IDs in brackets, e.g. "[8086:ad1d]"
 *   - revision suffixes, e.g. "(rev 01)"
 *   - trailing/duplicated commas and whitespace left behind after stripping.
 *
 * Examples:
 *   "0b.0 Processing accelerators [1200]: Intel Corporation Meteor Lake NPU [8086:7d1d] (rev 04)"
 *       -> "Intel Corporation Meteor Lake NPU"
 *   "Intel Corporation Meteor Lake-P [Intel Arc Graphics] [8086:7d55] (rev 08)"
 *       -> "Intel Corporation Meteor Lake-P [Intel Arc Graphics]"
 */
const cleanPlatform = (s?: string | null): string => {
  if (!s) return '';
  return s
    // Strip PCI bus/class prefix before vendor name (e.g. "0b.0 Processing accelerators [1200]: ")
    .replace(/^[0-9a-fA-F.]+\s+.*?\[\d+\]:\s*/, '')
    // Strip PCI vendor:device IDs like [8086:7d1d] but NOT human-readable brackets like [Intel Arc Graphics]
    .replace(/\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]/g, '')
    .replace(/\(rev\s+[0-9a-fA-F]+\)/gi, '')
    .replace(/\s*,\s*,/g, ',')
    .replace(/,\s*$/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
};

export function ConfigurationMetricsAccordion() {
  const platformData = useAppSelector((state) => state.metrics.platform);

  return (
    <Accordion title="Platform" defaultOpen>
      <div className="configuration-metrics">
        <div className="platform-configuration">
          <p><strong>Processor:</strong> {cleanPlatform(platformData?.Processor) || 'Loading...'}</p>
          <p><strong>NPU:</strong> {cleanPlatform(platformData?.NPU) || 'N/A'}</p>
          <p><strong>iGPU:</strong> {cleanPlatform(platformData?.iGPU) || 'N/A'}</p>
          <p><strong>Memory:</strong> {cleanPlatform(platformData?.Memory) || 'Loading...'}</p>
          <p><strong>Storage:</strong> {cleanPlatform(platformData?.Storage) || 'Loading...'}</p>
          <p><strong>OS:</strong> {cleanPlatform(platformData?.OS) || 'Linux'}</p>
        </div>
      </div>
    </Accordion>
  );
}

export default ConfigurationMetricsAccordion;