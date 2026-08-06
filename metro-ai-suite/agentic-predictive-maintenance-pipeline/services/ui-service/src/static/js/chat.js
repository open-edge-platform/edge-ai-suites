/* Copyright (C) 2026 Intel Corporation — SPDX-License-Identifier: Apache-2.0 */

(() => {
  "use strict";

  const form = document.getElementById("chat-form");
  if (!form) return;

  const messageInput = document.getElementById("chat-message");
  const runIdInput = document.getElementById("chat-run-id");
  const transcript = document.getElementById("chat-transcript");
  const emptyState = document.getElementById("chat-empty");
  const submitButton = document.getElementById("chat-submit");
  const status = document.getElementById("chat-status");
  const thinkingIndicator = document.getElementById("chat-thinking");
  const errorBox = document.getElementById("chat-error");
  const errorText = document.getElementById("chat-error-text");
  const retryButton = document.getElementById("chat-retry");
  const clearButton = document.getElementById("chat-clear");
  const defaultRunOption = document.getElementById("chat-default-run-option");
  const STORAGE_KEY_PREFIX = "apm.chat.history.v2";
  const MAX_STORED_MESSAGES = 100;
  let lastRequest = null;
  let pending = false;
  let chatHistory = [];

  function selectedMode() {
    return document.querySelector('input[name="chat-mode"]:checked').value;
  }

  function updateRunScopeLabel() {
    defaultRunOption.textContent = selectedMode() === "detections"
      ? "All stored detections"
      : "Latest completed run";
  }

  function historyStorageKey() {
    const runId = runIdInput.value.trim();
    return `${STORAGE_KEY_PREFIX}:${encodeURIComponent(runId || "default")}`;
  }

  function persistHistory() {
    try {
      sessionStorage.setItem(historyStorageKey(), JSON.stringify(chatHistory));
    } catch (error) {
      console.debug("Unable to save chat history for this browser session:", error);
    }
  }

  function removeStoredHistory() {
    try {
      sessionStorage.removeItem(historyStorageKey());
    } catch (error) {
      console.debug("Unable to remove chat history for this browser session:", error);
    }
  }

  function storedMessage(kind, text, options) {
    const message = { kind, text };
    if (typeof options.mode === "string") message.mode = options.mode;
    if (options.query !== undefined && options.query !== null) message.query = options.query;
    if (options.data !== undefined && options.data !== null) message.data = options.data;
    return message;
  }

  function appendMessage(kind, text, options = {}, save = true) {
    emptyState.hidden = true;
    const article = document.createElement("article");
    article.className = `chat-message chat-message-${kind}`;

    const heading = document.createElement("div");
    heading.className = "chat-message-heading";
    heading.textContent = kind === "user" ? "You" : "Assistant";
    if (options.mode) heading.textContent += ` · ${options.mode}`;
    article.appendChild(heading);

    const content = document.createElement("p");
    content.className = "chat-message-content";
    content.textContent = text;
    article.appendChild(content);

    if (options.query) {
      const query = document.createElement("p");
      query.className = "chat-response-query";
      const queryText = typeof options.query === "string"
        ? options.query
        : JSON.stringify(options.query);
      query.textContent = `Query: ${queryText}`;
      article.appendChild(query);
    }

    if (options.data !== undefined && options.data !== null) {
      const details = document.createElement("details");
      details.className = "chat-data";
      const summary = document.createElement("summary");
      summary.textContent = "View supporting data";
      const pre = document.createElement("pre");
      pre.textContent = typeof options.data === "string" ? options.data : JSON.stringify(options.data, null, 2);
      details.append(summary, pre);
      article.appendChild(details);
    }

    transcript.appendChild(article);
    transcript.scrollTop = transcript.scrollHeight;

    if (save) {
      chatHistory.push(storedMessage(kind, text, options));
      if (chatHistory.length > MAX_STORED_MESSAGES) {
        chatHistory = chatHistory.slice(-MAX_STORED_MESSAGES);
      }
      persistHistory();
    }
  }

  function restoreHistory() {
    let stored;
    try {
      stored = JSON.parse(sessionStorage.getItem(historyStorageKey()) || "[]");
    } catch (error) {
      console.debug("Unable to restore chat history for this browser session:", error);
      removeStoredHistory();
      return;
    }

    if (!Array.isArray(stored)) {
      removeStoredHistory();
      return;
    }

    chatHistory = stored.filter((message) => (
      message
      && (message.kind === "user" || message.kind === "assistant")
      && typeof message.text === "string"
      && message.text.length <= 100000
      && (message.mode === undefined || (
        typeof message.mode === "string" && message.mode.length <= 50
      ))
    )).slice(-MAX_STORED_MESSAGES);

    chatHistory.forEach((message) => {
      appendMessage(message.kind, message.text, {
        mode: message.mode,
        query: message.query,
        data: message.data,
      }, false);
    });

    if (chatHistory.length !== stored.length) persistHistory();
  }

  function showSelectedRunHistory() {
    transcript.querySelectorAll(".chat-message").forEach((message) => message.remove());
    chatHistory = [];
    lastRequest = null;
    errorBox.hidden = true;
    emptyState.hidden = false;
    restoreHistory();
    status.textContent = chatHistory.length
      ? "Chat history loaded for the selected run."
      : "No chat history for the selected run.";
  }

  function clearHistory() {
    transcript.querySelectorAll(".chat-message").forEach((message) => message.remove());
    chatHistory = [];
    removeStoredHistory();
    emptyState.hidden = false;
    lastRequest = null;
    errorBox.hidden = true;
    status.textContent = "Chat history cleared.";
    messageInput.focus();
  }

  function setPending(value) {
    pending = value;
    submitButton.disabled = value;
    messageInput.disabled = value;
    runIdInput.disabled = value;
    clearButton.disabled = value;
    document.querySelectorAll('input[name="chat-mode"]').forEach((input) => {
      input.disabled = value;
    });
    submitButton.textContent = value ? "Analyzing…" : "Send";
    status.textContent = value ? "Analyzing your question." : "";
    thinkingIndicator.hidden = !value;
    if (value) {
      transcript.appendChild(thinkingIndicator);
      transcript.scrollTop = transcript.scrollHeight;
    }
    transcript.setAttribute("aria-busy", String(value));
  }

  function showError(message) {
    errorText.textContent = message;
    errorBox.hidden = false;
    status.textContent = message;
  }

  async function sendRequest(request, appendUser = true) {
    if (pending) return;
    errorBox.hidden = true;
    if (appendUser) appendMessage("user", request.message);
    setPending(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(request),
      });

      let result;
      try {
        result = await response.json();
      } catch (_error) {
        throw new Error("The server returned an unreadable response.");
      }

      if (!response.ok) {
        const detail = typeof result.detail === "string" ? result.detail : "The request could not be completed.";
        throw new Error(detail);
      }
      if (!result || typeof result.answer !== "string") {
        throw new Error("The server response did not include an answer.");
      }

      thinkingIndicator.hidden = true;
      appendMessage("assistant", result.answer, {
        mode: typeof result.mode === "string" ? result.mode : request.mode,
        query: result.query,
        data: result.data,
      });
      status.textContent = "Answer received.";
      lastRequest = null;
    } catch (error) {
      lastRequest = request;
      showError(error instanceof Error ? error.message : "Unable to reach the chat service.");
    } finally {
      setPending(false);
      messageInput.focus();
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = messageInput.value.trim();
    if (!message || pending) {
      messageInput.focus();
      return;
    }

    const request = { message, mode: selectedMode() };
    const runId = runIdInput.value.trim();
    if (runId) request.run_id = runId;
    messageInput.value = "";
    sendRequest(request);
  });

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  document.querySelectorAll(".prompt-chip").forEach((button) => {
    button.addEventListener("click", () => {
      messageInput.value = button.dataset.prompt;
      messageInput.focus();
    });
  });

  retryButton.addEventListener("click", () => {
    if (lastRequest) sendRequest(lastRequest, false);
  });
  clearButton.addEventListener("click", clearHistory);
  runIdInput.addEventListener("change", showSelectedRunHistory);

  document.querySelectorAll('input[name="chat-mode"]').forEach((input) => {
    input.addEventListener("change", updateRunScopeLabel);
  });
  restoreHistory();
  updateRunScopeLabel();
})();
