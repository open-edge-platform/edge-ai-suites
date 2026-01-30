package org.intel;

import com.rti.dds.domain.DomainParticipant;
import com.rti.dds.domain.DomainParticipantFactory;
import com.rti.dds.infrastructure.*;
import com.rti.dds.subscription.*;
import com.rti.dds.topic.Topic;

import ice.Numeric;
import ice.NumericDataReader;
import ice.NumericSeq;

import ice.SampleArray;
import ice.SampleArrayDataReader;
import ice.SampleArraySeq;

public class MdPnpEventConsumer {

    public static void main(String[] args) throws InterruptedException {
        // Ensure GrpcPublisher is initialized so that the HTTP
        // control server (/start, /stop) is available immediately.
        GrpcPublisher.isStreamingEnabled();

        int domainId = Integer.parseInt(
                System.getenv().getOrDefault("DDS_DOMAIN", "10")
        );

        System.out.println(
                "DDS-Bridge waiting for /start on control server before subscribing to DDS domain "
                        + domainId
        );

        // Block here until /start is called on the control API,
        // which flips streamingEnabled to true.
        while (!GrpcPublisher.isStreamingEnabled()) {
            Thread.sleep(500);
        }

        System.out.println("🚀 Starting DDS Consumer on domain " + domainId);

        DomainParticipant participant =
                DomainParticipantFactory.TheParticipantFactory
                        .create_participant(
                                domainId,
                                DomainParticipantFactory.PARTICIPANT_QOS_DEFAULT,
                                null,
                                StatusKind.STATUS_MASK_NONE
                        );

        Subscriber subscriber =
                participant.create_subscriber(
                        DomainParticipant.SUBSCRIBER_QOS_DEFAULT,
                        null,
                        StatusKind.STATUS_MASK_NONE
                );

        /* ================= NUMERIC ================= */

        ice.NumericTypeSupport.register_type(
                participant,
                ice.NumericTypeSupport.get_type_name()
        );

        Topic numericTopic =
                participant.create_topic(
                        "Numeric",
                        ice.NumericTypeSupport.get_type_name(),
                        DomainParticipant.TOPIC_QOS_DEFAULT,
                        null,
                        StatusKind.STATUS_MASK_NONE
                );

        subscriber.create_datareader(
                numericTopic,
                Subscriber.DATAREADER_QOS_DEFAULT,
                new NumericListener(),
                StatusKind.DATA_AVAILABLE_STATUS
        );

        /* ================= WAVEFORM ================= */

        ice.SampleArrayTypeSupport.register_type(
                participant,
                ice.SampleArrayTypeSupport.get_type_name()
        );

        Topic waveformTopic =
                participant.create_topic(
                        "SampleArray",
                        ice.SampleArrayTypeSupport.get_type_name(),
                        DomainParticipant.TOPIC_QOS_DEFAULT,
                        null,
                        StatusKind.STATUS_MASK_NONE
                );

        subscriber.create_datareader(
                waveformTopic,
                Subscriber.DATAREADER_QOS_DEFAULT,
                new WaveformListener(),
                StatusKind.DATA_AVAILABLE_STATUS
        );

        System.out.println("✅ DDS Consumer started");
        Thread.sleep(Long.MAX_VALUE);
    }

     /* =========================================================
     * NUMERIC LISTENER
     * ========================================================= */    
    static class NumericListener extends DataReaderAdapter {

        private final NumericSeq dataSeq = new NumericSeq();
        private final SampleInfoSeq infoSeq = new SampleInfoSeq();

        @Override
        public void on_data_available(DataReader reader) {
            NumericDataReader numericReader = (NumericDataReader) reader;

            try {
                numericReader.take(
                        dataSeq,
                        infoSeq,
                        ResourceLimitsQosPolicy.LENGTH_UNLIMITED,
                        SampleStateKind.ANY_SAMPLE_STATE,
                        ViewStateKind.ANY_VIEW_STATE,
                        InstanceStateKind.ANY_INSTANCE_STATE
                );

                                for (int i = 0; i < dataSeq.size(); i++) {
                                        SampleInfo info = infoSeq.get(i);
                                        if (!info.valid_data) {
                                                continue;
                                        }

                                        Numeric n = dataSeq.get(i);

                                        VitalReading v = new VitalReading();
                                        v.deviceId = n.unique_device_identifier;
                                        v.metric = n.metric_id;
                                        v.value = n.value;
                                        v.unit = n.unit_id;
                                        v.timestamp = System.currentTimeMillis();

                                        // Only log and forward when DDS-bridge streaming is enabled
                                        if (GrpcPublisher.isStreamingEnabled()) {
                                                System.out.println("f6d1 Numeric Reading: " + v.toString());
                                                // push to gRPC (gated again inside GrpcPublisher)
                                                GrpcPublisher.publish(v);
                                        }
                                }
            } finally {
                numericReader.return_loan(dataSeq, infoSeq);
            }
        }
    }


    /* =========================================================
     * WAVEFORM LISTENER
     * ========================================================= */
    static class WaveformListener extends DataReaderAdapter {

        private final SampleArraySeq dataSeq = new SampleArraySeq();
        private final SampleInfoSeq infoSeq = new SampleInfoSeq();

        @Override
        public void on_data_available(DataReader reader) {

            SampleArrayDataReader waveformReader =
                    (SampleArrayDataReader) reader;

            try {
                waveformReader.take(
                        dataSeq,
                        infoSeq,
                        ResourceLimitsQosPolicy.LENGTH_UNLIMITED,
                        SampleStateKind.ANY_SAMPLE_STATE,
                        ViewStateKind.ANY_VIEW_STATE,
                        InstanceStateKind.ANY_INSTANCE_STATE
                );

                for (int i = 0; i < dataSeq.size(); i++) {
                    SampleInfo info = infoSeq.get(i);
                    if (!info.valid_data) {
                        continue;
                    }

                    SampleArray w = dataSeq.get(i);

                                        // Values is a wrapper around a FloatSeq called userData
                                        int sampleCount = (w.values != null && w.values.userData != null)
                                                                        ? w.values.userData.size()
                                                                        : 0;

                                        // Only emit waveform logs (and forward) when streaming is enabled
                                        if (GrpcPublisher.isStreamingEnabled()) {
                                                System.out.printf(
                                                                "📈 WAVEFORM | device=%s metric=%s freq=%dHz samples=%d%n",
                                                                w.unique_device_identifier,
                                                                w.metric_id,
                                                                w.frequency,
                                                                sampleCount
                                                );

                                                // Build VitalReading with waveform payload
                                                VitalReading v = new VitalReading();
                                                v.deviceId = w.unique_device_identifier;
                                                v.metric = w.metric_id;
                                                v.value = 0; // scalar value not meaningful for waveform
                                                v.unit = w.unit_id;
                                                v.timestamp = System.currentTimeMillis();
                                                v.waveformFrequencyHz = (int) w.frequency;

                                                if (sampleCount > 0) {
                                                        java.util.List<Float> samples = new java.util.ArrayList<>(sampleCount);
                                                        for (int j = 0; j < sampleCount; j++) {
                                                                samples.add((Float) w.values.userData.get(j));
                                                        }
                                                        v.waveform = samples;
                                                }

                                                System.out.println("🛑 Waveform Reading: " + v.toString());
                                                // push to gRPC (gated again inside GrpcPublisher)
                                                GrpcPublisher.publish(v);
                                        }
                }
            } finally {
                waveformReader.return_loan(dataSeq, infoSeq);
            }
        }
    }
}
