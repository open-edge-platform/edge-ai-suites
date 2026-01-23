package org.intel;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.stub.StreamObserver;
import org.intel.grpc.Vital;
import org.intel.grpc.VitalServiceGrpc;
import com.google.protobuf.Empty;

public final class GrpcPublisher {

    private static final ManagedChannel channel;
    private static final StreamObserver<Vital> requestObserver;

    static {
        String host = System.getenv().getOrDefault("GRPC_HOST", "localhost");
        int port = Integer.parseInt(System.getenv().getOrDefault("GRPC_PORT", "50051"));

        channel = ManagedChannelBuilder
                .forAddress(host, port)
                .usePlaintext()
                .build();

        VitalServiceGrpc.VitalServiceStub stub =
                VitalServiceGrpc.newStub(channel);

        // 🔥 Open ONE stream
        requestObserver = stub.streamVitals(new StreamObserver<Empty>() {
            @Override
            public void onNext(Empty value) {
                // aggregator acknowledged stream end
            }

            @Override
            public void onError(Throwable t) {
                System.err.println("gRPC stream error: " + t.getMessage());
            }

            @Override
            public void onCompleted() {
                System.out.println("gRPC stream completed");
            }
        });

        Runtime.getRuntime().addShutdownHook(new Thread(GrpcPublisher::shutdown));

        System.out.println("gRPC streaming connected to " + host + ":" + port);
    }

    private GrpcPublisher() {}

    public static void publish(VitalReading v) {
        if (v == null) return;

        Vital msg = Vital.newBuilder()
                .setDeviceId(v.deviceId)
                .setMetric(v.metric)
                .setValue(v.value)
                .setUnit(v.unit)
                .setTimestamp(v.timestamp)
                .build();

        requestObserver.onNext(msg); // 🔥 STREAM WRITE
    }

    public static void shutdown() {
        try {
            requestObserver.onCompleted();
        } catch (Exception ignored) {}

        channel.shutdown();
    }
}
