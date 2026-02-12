import React, { useState } from 'react';
import { WORKLOAD_INFO, VITAL_SIGNS_INFO, MEDICAL_UNITS, ECG_CLASSIFICATIONS } from '../../constants';
import '../../assets/css/InfoModal.css';

interface InfoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const InfoModal: React.FC<InfoModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'workloads' | 'vitals' | 'ecg' | 'units'>('workloads');

  if (!isOpen) return null;

  return (
    <div className="info-modal-overlay" onClick={onClose}>
      <div className="info-modal" onClick={(e) => e.stopPropagation()}>
        <div className="info-modal-header">
          <h2>Medical Reference Guide</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Tab Navigation */}
        <div className="info-tabs">
          <button 
            className={`tab ${activeTab === 'workloads' ? 'active' : ''}`}
            onClick={() => setActiveTab('workloads')}
          >
            Workloads
          </button>
          <button 
            className={`tab ${activeTab === 'vitals' ? 'active' : ''}`}
            onClick={() => setActiveTab('vitals')}
          >
            Vital Signs
          </button>
          <button 
            className={`tab ${activeTab === 'ecg' ? 'active' : ''}`}
            onClick={() => setActiveTab('ecg')}
          >
            ECG Codes
          </button>
          <button 
            className={`tab ${activeTab === 'units' ? 'active' : ''}`}
            onClick={() => setActiveTab('units')}
          >
            Units
          </button>
        </div>
        
        <div className="info-modal-content">
          {/* Workloads Tab */}
          {activeTab === 'workloads' && (
            <section className="info-section">
              <div className="info-list">
                {WORKLOAD_INFO.map((workload) => (
                  <div key={workload.id} className="info-card workload-card">
                    <div className="workload-header">
                      <h3>{workload.name} - {workload.fullName}</h3>
                    </div>
                    <p className="workload-description">{workload.description}</p>
                    
                    <div className="info-metrics">
                      <strong>Monitored Metrics:</strong>
                      <div className="metrics-list">
                        {workload.metrics.map((metric) => (
                          <span key={metric} className="metric-badge">{metric}</span>
                        ))}
                      </div>
                    </div>

                    <div className="medical-terms">
                      <strong>Medical Terminology:</strong>
                      {workload.medicalTerms.map((term) => (
                        <div key={term.term} className="term-item">
                          <div className="term-header">
                            <span className="term-abbr">{term.term}</span>
                            <span className="term-separator">→</span>
                            <span className="term-full">{term.full}</span>
                          </div>
                          <p className="term-def">{term.definition}</p>
                          {term.normalRange && (
                            <span className="term-range">✓ Normal: {term.normalRange}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Vital Signs Tab */}
          {activeTab === 'vitals' && (
            <section className="info-section">
              <div className="info-list">
                {VITAL_SIGNS_INFO.map((vital) => (
                  <div key={vital.key} className="info-card vital-card">
                    <div className="vital-header">
                      <h3>{vital.fullForm}</h3>
                      <span className="vital-unit-badge">{vital.unit}</span>
                    </div>
                    <p className="vital-description">{vital.description}</p>
                    
                    <div className="vital-ranges">
                      <div className="range-item normal">
                        <strong>✓ Normal:</strong> {vital.normalRange}
                      </div>
                      {vital.criticalLow && (
                        <div className="range-item critical-low">
                          <strong>⚠️ Critical Low:</strong> {vital.criticalLow}
                        </div>
                      )}
                      {vital.criticalHigh !== 'N/A' && vital.criticalHigh && (
                        <div className="range-item critical-high">
                          <strong>⚠️ Critical High:</strong> {vital.criticalHigh}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ECG Classifications Tab */}
          {activeTab === 'ecg' && (
            <section className="info-section">
              <h3 className="section-title">AI-ECG Classification Codes</h3>
              <div className="info-list">
                {ECG_CLASSIFICATIONS.map((ecg) => (
                  <div key={ecg.code} className="info-card ecg-card">
                    <div className="ecg-header">
                      <span className="ecg-code">{ecg.code}</span>
                      <h4>{ecg.name}</h4>
                    </div>
                    <p>{ecg.description}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Medical Units Tab */}
          {activeTab === 'units' && (
            <section className="info-section">
              <h3 className="section-title">Measurement Units Reference</h3>
              <div className="info-list">
                {MEDICAL_UNITS.map((unit) => (
                  <div key={unit.unit} className="info-card unit-card">
                    <div className="unit-header">
                      <span className="unit-abbr">{unit.unit}</span>
                      <span className="unit-separator">→</span>
                      <span className="unit-full">{unit.fullForm}</span>
                    </div>
                    <p className="unit-usage">{unit.usage}</p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

export default InfoModal;