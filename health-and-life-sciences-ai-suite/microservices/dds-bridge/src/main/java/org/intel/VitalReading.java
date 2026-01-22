package org.intel; 
 
 class VitalReading {   
    public String deviceId;
    public String metric;
    public double value;
    public String unit;
    public long timestamp;
    public VitalReading(String deviceId, String metric, double value, String unit, long timestamp) {
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

    public String toString() {
        return "VitalReading [deviceId=" + deviceId + ", metric=" + metric + ", value=" + value + ", unit=" + unit
                + ", timestamp=" + timestamp + "]";
    }
 }