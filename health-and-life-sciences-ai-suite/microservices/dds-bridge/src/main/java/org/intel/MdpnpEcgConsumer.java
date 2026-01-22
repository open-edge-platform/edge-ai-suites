// package org.intel;

// import com.rti.dds.domain.*;
// import com.rti.dds.infrastructure.*;
// import com.rti.dds.subscription.*;
// import com.rti.dds.topic.*;
// import org.mdpnp.rtiapi.data.DeviceIdentity.DeviceIdentityDataReader;
// import org.mdpnp.rtiapi.data.DeviceIdentity.DeviceIdentityDataReaderHelper;

// import org.mdpnp.rtiapi.data.Numeric.NumericDataReader;
// import org.mdpnp.rtiapi.data.Numeric.NumericDataReaderHelper;

// import org.mdpnp.rtiapi.data.Waveform.WaveformDataReader;
// import org.mdpnp.rtiapi.data.Waveform.WaveformTypeSupport;

// import ice.*;

// import java.util.HashMap;
// import java.util.Map;

// public class MdpnpEcgConsumer {

//     private static final int DOMAIN_ID = 10;

//     private static final Map<String, String> deviceMap = new HashMap<>();

//     public static void main(String[] args) throws Exception {

//         DomainParticipant participant =
//                 DomainParticipantFactory.TheParticipantFactory
//                         .create_participant(
//                                 DOMAIN_ID,
//                                 DomainParticipantFactory.PARTICIPANT_QOS_DEFAULT,
//                                 null,
//                                 StatusKind.STATUS_MASK_NONE
//                         );

//         Subscriber subscriber =
//                 participant.create_subscriber(
//                         DomainParticipant.SUBSCRIBER_QOS_DEFAULT,
//                         null,
//                         StatusKind.STATUS_MASK_NONE
//                 );

//         /* ---------------- DeviceIdentity ---------------- */

//         Topic deviceTopic = participant.create_topic(
//                 "DeviceIdentity",
//                 DeviceIdentityTypeSupport.get_type_name(),
//                 DomainParticipant.TOPIC_QOS_DEFAULT,
//                 null,
//                 StatusKind.STATUS_MASK_NONE
//         );

//         DeviceIdentityDataReader deviceReader =
//                 DeviceIdentityDataReaderHelper.narrow(
//                         subscriber.create_datareader(
//                                 deviceTopic,
//                                 Subscriber.DATAREADER_QOS_DEFAULT,
//                                 null,
//                                 StatusKind.STATUS_MASK_NONE
//                         )
//                 );

//         /* ---------------- Numeric ---------------- */

//         Topic numericTopic = participant.create_topic(
//                 "Numeric",
//                 NumericTypeSupport.get_type_name(),
//                 DomainParticipant.TOPIC_QOS_DEFAULT,
//                 null,
//                 StatusKind.STATUS_MASK_NONE
//         );

//         NumericDataReader numericReader =
//                 NumericDataReaderHelper.narrow(
//                         subscriber.create_datareader(
//                                 numericTopic,
//                                 Subscriber.DATAREADER_QOS_DEFAULT,
//                                 null,
//                                 StatusKind.STATUS_MASK_NONE
//                         )
//                 );

//         /* ---------------- Waveform ---------------- */

//         Topic waveformTopic = participant.create_topic(
//                 "Waveform",
//                 WaveformTypeSupport.get_type_name(),
//                 DomainParticipant.TOPIC_QOS_DEFAULT,
//                 null,
//                 StatusKind.STATUS_MASK_NONE
//         );

//         WaveformDataReader waveformReader =
//                 WaveformDataReaderHelper.narrow(
//                         subscriber.create_datareader(
//                                 waveformTopic,
//                                 Subscriber.DATAREADER_QOS_DEFAULT,
//                                 null,
//                                 StatusKind.STATUS_MASK_NONE
//                         )
//                 );

//         System.out.println("✅ ECG DDS Consumer started (domain " + DOMAIN_ID + ")");

//         DeviceIdentitySeq deviceSeq = new DeviceIdentitySeq();
//         NumericSeq numericSeq = new NumericSeq();
//         WaveformSeq waveformSeq = new WaveformSeq();

//         SampleInfoSeq infoSeq = new SampleInfoSeq();

//         while (true) {

//             /* -------- DeviceIdentity -------- */
//             deviceReader.take(
//                     deviceSeq,
//                     infoSeq,
//                     ResourceLimitsQosPolicy.LENGTH_UNLIMITED,
//                     SampleStateKind.ANY_SAMPLE_STATE,
//                     ViewStateKind.ANY_VIEW_STATE,
//                     InstanceStateKind.ANY_INSTANCE_STATE
//             );

//             for (int i = 0; i < deviceSeq.size(); i++) {
//                 DeviceIdentity di = deviceSeq.get(i);
//                 deviceMap.put(di.unique_device_identifier, di.model);
//             }
//             deviceReader.return_loan(deviceSeq, infoSeq);

//             /* -------- Numeric (Heart Rate) -------- */
//             numericReader.take(
//                     numericSeq,
//                     infoSeq,
//                     ResourceLimitsQosPolicy.LENGTH_UNLIMITED,
//                     SampleStateKind.ANY_SAMPLE_STATE,
//                     ViewStateKind.ANY_VIEW_STATE,
//                     InstanceStateKind.ANY_INSTANCE_STATE
//             );

//             for (int i = 0; i < numericSeq.size(); i++) {
//                 Numeric n = numericSeq.get(i);

//                 if ("ECG_Simulator".equals(deviceMap.get(n.unique_device_identifier))
//                         && "MDC_ECG_HEART_RATE".equals(n.metric_id)) {

//                     System.out.printf(
//                             "❤️ HR [%s] = %.1f %s%n",
//                             n.unique_device_identifier,
//                             n.value,
//                             n.unit_id
//                     );
//                 }
//             }
//             numericReader.return_loan(numericSeq, infoSeq);

//             /* -------- Waveform (ECG) -------- */
//             waveformReader.take(
//                     waveformSeq,
//                     infoSeq,
//                     ResourceLimitsQosPolicy.LENGTH_UNLIMITED,
//                     SampleStateKind.ANY_SAMPLE_STATE,
//                     ViewStateKind.ANY_VIEW_STATE,
//                     InstanceStateKind.ANY_INSTANCE_STATE
//             );

//             for (int i = 0; i < waveformSeq.size(); i++) {
//                 Waveform wf = waveformSeq.get(i);

//                 if ("ECG_Simulator".equals(deviceMap.get(wf.unique_device_identifier))
//                         && wf.metric_id.startsWith("MDC_ECG")) {

//                     System.out.printf(
//                             "📈 ECG %s | lead=%s | samples=%d | freq=%dHz%n",
//                             wf.unique_device_identifier,
//                             wf.metric_id,
//                             wf.samples.userData.length,
//                             wf.frequency
//                     );
//                 }
//             }
//             waveformReader.return_loan(waveformSeq, infoSeq);

//             Thread.sleep(200);
//         }
//     }
// }
