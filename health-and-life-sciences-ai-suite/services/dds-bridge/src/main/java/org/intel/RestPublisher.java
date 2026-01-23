package org.intel;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.HttpURLConnection;
import java.net.URL;

public class RestPublisher {

    private static final ObjectMapper mapper = new ObjectMapper();
    private static final String ENDPOINT = "http://localhost:8080/vitals";

    public static void publish(VitalReading v) {
        try {
            String json = mapper.writeValueAsString(v);

            HttpURLConnection conn =
                (HttpURLConnection) new URL(ENDPOINT).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            conn.getOutputStream().write(json.getBytes());
            conn.getResponseCode(); // fire-and-forget
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
