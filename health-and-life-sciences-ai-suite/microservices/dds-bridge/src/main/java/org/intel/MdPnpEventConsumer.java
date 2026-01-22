package org.intel;

import com.rti.dds.domain.DomainParticipant;
import com.rti.dds.domain.DomainParticipantFactory;
import com.rti.dds.infrastructure.*;
import com.rti.dds.subscription.*;
import com.rti.dds.topic.Topic;

import ice.Numeric;
import ice.NumericDataReader;
import ice.NumericSeq;

public class MdPnpEventConsumer {

    public static void main(String[] args) throws InterruptedException {

        int domainId = Integer.parseInt(
                System.getenv().getOrDefault("DDS_DOMAIN", "10")
        );

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

        // Register ICE Numeric type
        ice.NumericTypeSupport.register_type(
                participant,
                ice.NumericTypeSupport.get_type_name()
        );

        Topic topic =
                participant.create_topic(
                        "Numeric",
                        ice.NumericTypeSupport.get_type_name(),
                        DomainParticipant.TOPIC_QOS_DEFAULT,
                        null,
                        StatusKind.STATUS_MASK_NONE
                );

        DataReader reader =
                subscriber.create_datareader(
                        topic,
                        Subscriber.DATAREADER_QOS_DEFAULT,
                        new NumericListener(),
                        StatusKind.DATA_AVAILABLE_STATUS
                );

        System.out.println("✅ DDS Bridge started. Waiting for Numeric data...");
        Thread.sleep(Long.MAX_VALUE);
    }

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
                    if (info.valid_data) {
                        Numeric n = dataSeq.get(i);

                        // System.out.printf(
                        //         "📊 %s | %s = %.2f %s%n",
                        //         n.unique_device_identifier,
                        //         n.metric_id,
                        //         n.value,
                        //         n.unit_id
                        // );
                        VitalReading v = new VitalReading();
                        v.deviceId = n.unique_device_identifier;
                        v.metric = n.metric_id;
                        v.value = n.value;
                        v.unit = n.unit_id;
                        v.timestamp = System.currentTimeMillis();
                        System.out.println("🛑 Vital Reading: " + v.toString());

                        // push to gRPC
                        GrpcPublisher.publish(v);
                    }
                }
            } finally {
                numericReader.return_loan(dataSeq, infoSeq);
            }
        }
    }
}
