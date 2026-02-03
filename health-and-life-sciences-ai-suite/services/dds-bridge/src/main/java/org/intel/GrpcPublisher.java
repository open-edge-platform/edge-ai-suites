package org.intel;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.stub.StreamObserver;
import org.intel.grpc.Vital;
import org.intel.grpc.VitalServiceGrpc;
import com.google.protobuf.Empty;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.concurrent.Executors;

public final class GrpcPublisher {

    private static final ManagedChannel channel;
    private static final VitalServiceGrpc.VitalServiceStub stub;

    // Active gRPC stream to the aggregator (created lazily on /start).
    private static volatile StreamObserver<Vital> requestObserver;

    // Global gate to control whether DDS readings are forwarded to
    // the aggregator. Default is OFF; /start must be called to enable.
    private static volatile boolean streamingEnabled = false;

    static {
        String host = System.getenv().getOrDefault("GRPC_HOST", "localhost");
        int port = Integer.parseInt(System.getenv().getOrDefault("GRPC_PORT", "50051"));

        channel = ManagedChannelBuilder
                .forAddress(host, port)
                .usePlaintext()
                .build();

        stub = VitalServiceGrpc.newStub(channel);

        Runtime.getRuntime().addShutdownHook(new Thread(GrpcPublisher::shutdown));

        System.out.println("gRPC channel created towards " + host + ":" + port);

        // Start lightweight HTTP control server on DDS_CONTROL_PORT
        // so that aggregator-service (or other callers) can toggle
        // streaming via /start and /stop.
        int controlPort = Integer.parseInt(
                System.getenv().getOrDefault("DDS_CONTROL_PORT", "8082")
        );
        startControlServer(controlPort);
    }

    private GrpcPublisher() {}

    public static boolean isStreamingEnabled() {
        return streamingEnabled;
    }

    public static void setStreamingEnabled(boolean enabled) {
        streamingEnabled = enabled;
        String state = enabled ? "ENABLED" : "DISABLED";
        System.out.println("[DDS-Bridge] Streaming " + state);

        if (enabled) {
            // (Re)open a streaming RPC when streaming is enabled.
            // This avoids using a stale observer if the previous
            // stream failed with UNAVAILABLE or similar.
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
        } else {
            // When disabling streaming, close the current stream if any.
            StreamObserver<Vital> observer = requestObserver;
            requestObserver = null;
            if (observer != null) {
                try {
                    observer.onCompleted();
                } catch (Exception ignored) {}
            }
        }
    }

    public static void publish(VitalReading v) {
        if (v == null) return;

        // Do not forward anything to the aggregator until streaming
        // has been explicitly enabled via the /start control API and
        // a streaming RPC is active.
        StreamObserver<Vital> observer = requestObserver;
        if (!streamingEnabled || observer == null) {
            return;
        }

        Vital.Builder builder = Vital.newBuilder()
                .setDeviceId(v.deviceId)
                .setMetric(v.metric)
                .setValue(v.value)
                .setUnit(v.unit)
                .setTimestamp(v.timestamp);

        // Attach waveform payload if present
        if (v.waveform != null && !v.waveform.isEmpty()) {
            builder.addAllWaveform(v.waveform);
            builder.setWaveformFrequencyHz(v.waveformFrequencyHz);
        }

        // Attach device_type as metadata so the aggregator/UI can
        // distinguish between different MDPNP simulators.
        if (v.deviceType != null && !v.deviceType.isEmpty()) {
            builder.putMetadata("device_type", v.deviceType);
        }

        Vital msg = builder.build();
        try {
            observer.onNext(msg);
        } catch (Exception e) {
            System.err.println("Failed to send Vital over gRPC: " + e.getMessage());
        }
    }

    public static void shutdown() {
        StreamObserver<Vital> observer = requestObserver;
        requestObserver = null;
        if (observer != null) {
            try {
                observer.onCompleted();
            } catch (Exception ignored) {}
        }
        channel.shutdown();
    }

    private static void startControlServer(int port) {
        try {
            HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

            server.createContext("/start", new HttpHandler() {
                @Override
                public void handle(HttpExchange exchange) throws IOException {
                    if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        exchange.sendResponseHeaders(405, -1);
                        return;
                    }
                    setStreamingEnabled(true);
                    String response = "{\"status\":\"started\"}";
                    exchange.getResponseHeaders().add("Content-Type", "application/json");
                    byte[] bytes = response.getBytes();
                    exchange.sendResponseHeaders(200, bytes.length);
                    try (OutputStream os = exchange.getResponseBody()) {
                        os.write(bytes);
                    }
                }
            });

            server.createContext("/stop", new HttpHandler() {
                @Override
                public void handle(HttpExchange exchange) throws IOException {
                    if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        exchange.sendResponseHeaders(405, -1);
                        return;
                    }
                    setStreamingEnabled(false);
                    String response = "{\"status\":\"stopped\"}";
                    exchange.getResponseHeaders().add("Content-Type", "application/json");
                    byte[] bytes = response.getBytes();
                    exchange.sendResponseHeaders(200, bytes.length);
                    try (OutputStream os = exchange.getResponseBody()) {
                        os.write(bytes);
                    }
                }
            });

            server.setExecutor(Executors.newSingleThreadExecutor());
            server.start();
            System.out.println("[DDS-Bridge] Control server listening on port " + port + " (/start, /stop)");
        } catch (IOException e) {
            System.err.println("[DDS-Bridge] Failed to start control server: " + e.getMessage());
        }
    }
}
