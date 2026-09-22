// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { getChatSessionId } from "@/utils/common";
import { message } from "ant-design-vue";

export interface StreamController {
  cancel: () => void;
}

export const handleMessageSend = (
  url: string,
  postData: any,
  onDisplay: (data: string) => void,
  onEnd?: () => void,
): StreamController => {
  let reader: ReadableStreamDefaultReader | undefined;
  const controller = new AbortController();

  const processSseLine = (line: string) => {
    if (!line.startsWith("data: ")) {
      return;
    }

    const data = line.slice(6).trim();
    if (!data || data === "[DONE]") {
      return;
    }

    try {
      const json = JSON.parse(data);
      const text = json.choices?.[0]?.delta?.content;
      if (text) {
        onDisplay(text);
      }
    } catch (parseError) {
      console.warn("Failed to parse SSE data:", parseError, data);
    }
  };

  const execute = async () => {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          Authorization: "d7932a214e75f67d196d2588584aaa78606e30f62ddf2212",
          "x-openclaw-session-key": getChatSessionId(),
        },
        body: JSON.stringify(postData),
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorMessage = "";
        try {
          const errorText = await response.text();
          if (errorText) {
            errorMessage = errorText;
          }
        } catch (parseError) {
          console.warn("Failed to read error response:", parseError);
        }
        message.error(errorMessage || "Request failed");
        onEnd?.();
        return;
      }

      reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Readable stream is not available");
      }

      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          const remainingLine = buffer.trim();
          if (remainingLine) {
            processSseLine(remainingLine);
          }
          onEnd?.();
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        lines.forEach((line) => {
          processSseLine(line.trim());
        });
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log("Stream was aborted by user.");
      } else {
        console.error("Request or stream error:", error);
        if (error.message !== "Request failed") {
          message.error(error.message || "Stream error");
        }
      }
      onEnd?.();
    } finally {
      if (reader) {
        try {
          await reader.cancel();
        } catch (cancelError) {
          console.warn("Failed to cancel reader:", cancelError);
        }
      }
    }
  };

  execute().catch(console.error);

  return {
    cancel: () => {
      if (!controller.signal.aborted) {
        controller.abort();
      }
    },
  };
};
