package org.intel;

import java.util.List;

class VitalReading {

    public String deviceId;
    public String metric;
    public double value;
    public String unit;
    public long timestamp;

    // Logical device type (e.g., IBP_Simulator, ECG_Simulator);
    // inferred in MdPnpEventConsumer from metric / device id.
    public String deviceType;

    // Optional waveform payload (for SampleArray / ECG etc.)
    public List<Float> waveform;          // samples in acquisition order
    public int waveformFrequencyHz;       // sampling rate associated with waveform

    public VitalReading(String deviceId,
                        String metric,
                        double value,
                        String unit,
                        long timestamp) {
        this.deviceId = deviceId;
        this.metric = metric;
        this.value = value;
        this.unit = unit;
        this.timestamp = timestamp;
    }

    public VitalReading() {
    }

    //getters and setters
    public String getDeviceId() {
        return deviceId;
    }

    public void setDeviceId(String deviceId) {
        this.deviceId = deviceId;
    }

    public String getMetric() {
        return metric;
    }

    public void setMetric(String metric) {
        this.metric = metric;
    }

    public double getValue() {
        return value;
    }

    public void setValue(double value) {
        this.value = value;
    }

    public String getUnit() {
        return unit;
    }

    public void setUnit(String unit) {
        this.unit = unit;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public String getDeviceType() {
        return deviceType;
    }

    public void setDeviceType(String deviceType) {
        this.deviceType = deviceType;
    }

    public List<Float> getWaveform() {
        return waveform;
    }

    public void setWaveform(List<Float> waveform) {
        this.waveform = waveform;
    }

    public int getWaveformFrequencyHz() {
        return waveformFrequencyHz;
    }

    public void setWaveformFrequencyHz(int waveformFrequencyHz) {
        this.waveformFrequencyHz = waveformFrequencyHz;
    }

    @Override
    public String toString() {
        return "VitalReading [deviceId=" + deviceId +
            ", metric=" + metric +
            ", value=" + value +
            ", unit=" + unit +
            ", timestamp=" + timestamp +
            ", deviceType=" + deviceType +
            ", waveformSamples=" + (waveform == null ? 0 : waveform.size()) +
            ", waveformFrequencyHz=" + waveformFrequencyHz +
            "]";
    }
}