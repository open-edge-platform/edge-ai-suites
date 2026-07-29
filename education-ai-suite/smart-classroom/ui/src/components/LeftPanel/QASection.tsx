import React, { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/QASection.css";
import { csQaAsk, type QAChatMessage, type QASource } from "../../services/api";
import { useAppSelector } from "../../redux/hooks";
import noSearchIcon from "../../assets/images/no-search-icon.svg";

const MAX_QUESTION_LENGTH = 500;

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: QASource[];
  isError?: boolean;
}

function formatVideoTime(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function getSourceLabel(src: QASource): string {
  const name = src.file_name ?? src.file_path?.split("/").pop() ?? "Unknown file";
  if (src.type === "video" && src.video_pin_second != null) {
    return `${name} @ ${formatVideoTime(src.video_pin_second)}`;
  }
  return name;
}

function getSourceTypeIcon(type: string | null): string {
  if (type === "video") return "🎬";
  if (type === "image") return "🖼️";
  return "📄";
}

function genId(): string {
  return Math.random().toString(36).slice(2);
}

const QASection: React.FC = () => {
  const { t } = useTranslation();
  const csUploadsComplete = useAppSelector((s) => s.ui.csUploadsComplete);
  const csHasUploads = useAppSelector((s) => s.ui.csHasUploads);
  const csTags = useAppSelector((s) => s.ui.csTags);

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Optional tag filter — mirrors the behaviour in SearchSection
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [isTagDropdownOpen, setIsTagDropdownOpen] = useState(false);
  const tagBoxRef = useRef<HTMLDivElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to the bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Close tag dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (tagBoxRef.current && !tagBoxRef.current.contains(e.target as Node)) {
        setIsTagDropdownOpen(false);
      }
    };
    if (isTagDropdownOpen) {
      document.addEventListener("mousedown", handler);
    }
    return () => document.removeEventListener("mousedown", handler);
  }, [isTagDropdownOpen]);

  // Remove tags that no longer exist in uploaded files
  useEffect(() => {
    setSelectedTags((prev) => prev.filter((t) => csTags.includes(t)));
  }, [csTags]);

  // Reset chat when uploads are cleared
  useEffect(() => {
    if (!csHasUploads) {
      setMessages([]);
      setInput("");
      setSelectedTags([]);
    }
  }, [csHasUploads]);

  const toggleTag = useCallback((tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }, []);

  const removeTag = useCallback((tag: string) => {
    setSelectedTags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading || !csUploadsComplete) return;

    // Append user message immediately
    const userEntry: ChatEntry = { id: genId(), role: "user", content: question };
    setMessages((prev) => [...prev, userEntry]);
    setInput("");

    setIsLoading(true);
    try {
      // Build the history payload from existing messages (exclude the one we just added)
      const history: QAChatMessage[] = messages
        .filter((m) => !m.isError)
        .map((m) => ({ role: m.role, content: m.content }));

      const filter =
        selectedTags.length > 0 ? { tags: selectedTags } : undefined;

      const result = await csQaAsk({
        question,
        history,
        filter,
      });

      const assistantEntry: ChatEntry = {
        id: genId(),
        role: "assistant",
        content: result.answer,
        sources: result.sources,
      };
      setMessages((prev) => [...prev, assistantEntry]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong. Please try again.";
      const errorEntry: ChatEntry = {
        id: genId(),
        role: "assistant",
        content: msg,
        isError: true,
      };
      setMessages((prev) => [...prev, errorEntry]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (without Shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setInput("");
  };

  const canSend = input.trim().length > 0 && !isLoading && csUploadsComplete;

  // ── Disabled states ──────────────────────────────────────────────────────
  const renderDisabled = (title: string, hint: string) => (
    <div className="cs-qa-disabled">
      <img src={noSearchIcon} alt="Q&A unavailable" className="cs-qa-disabled-icon" />
      <span className="cs-qa-disabled-title">{title}</span>
      <span className="cs-qa-disabled-hint">{hint}</span>
    </div>
  );

  return (
    <div className="cs-qa-content">
      {/* ── Disabled: no uploads ── */}
      {!csHasUploads
        ? renderDisabled(
            t("qaSection.notAvailable", "Q&A Not Available"),
            t("qaSection.uploadHint", "Upload files to start chatting")
          )
        : !csUploadsComplete
        ? renderDisabled(
            t("qaSection.notAvailable", "Q&A Not Available"),
            t("qaSection.processingHint", "Files are still uploading...")
          )
        : /* ── Active state ── */ (
              <>
                {/* ── Optional tag filter ── */}
                {csTags.length > 0 && (
                  <div className="cs-qa-filter-row">
                    <span className="cs-qa-filter-label">
                      {t("qaSection.filterByLabel", "Filter by label:")}
                    </span>
                    <div className="cs-qa-tag-filter" ref={tagBoxRef}>
                      <div
                        className="cs-qa-tag-trigger"
                        onClick={() => setIsTagDropdownOpen((o) => !o)}
                      >
                        {selectedTags.length === 0
                          ? t("qaSection.allContent", "All content")
                          : selectedTags.map((tag) => (
                              <span key={tag} className="cs-qa-tag-chip">
                                {tag}
                                <button
                                  className="cs-qa-tag-chip-remove"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    removeTag(tag);
                                  }}
                                >
                                  ×
                                </button>
                              </span>
                            ))}
                        <svg
                          className={`cs-qa-tag-chevron ${isTagDropdownOpen ? "open" : ""}`}
                          width="12"
                          height="12"
                          viewBox="0 0 12 12"
                          fill="none"
                        >
                          <path
                            d="M2 4L6 8L10 4"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                          />
                        </svg>
                      </div>
                      {isTagDropdownOpen && (
                        <div className="cs-qa-tag-dropdown">
                          {csTags.map((tag) => (
                            <label key={tag} className="cs-qa-tag-option">
                              <input
                                type="checkbox"
                                checked={selectedTags.includes(tag)}
                                onChange={() => toggleTag(tag)}
                              />
                              {tag}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* ── Messages toolbar: clear button ── */}
                {messages.length > 0 && (
                  <div className="cs-qa-toolbar">
                    <button
                      className="cs-qa-clear-btn"
                      onClick={handleClearChat}
                      title={t("qaSection.clearChat", "Clear conversation")}
                    >
                      {t("qaSection.clearChat", "Clear conversation")}
                    </button>
                  </div>
                )}

                {/* ── Message history ── */}
                <div className="cs-qa-messages">
                  {messages.length === 0 && (
                    <div className="cs-qa-empty-hint">
                      <span>{t("qaSection.emptyHint", "Ask anything about your uploaded content.")}</span>
                    </div>
                  )}

                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`cs-qa-message cs-qa-message--${msg.role}${msg.isError ? " cs-qa-message--error" : ""}`}
                    >
                      <div className="cs-qa-bubble">{msg.content}</div>

                      {/* Sources */}
                      {msg.role === "assistant" &&
                        !msg.isError &&
                        msg.sources &&
                        msg.sources.length > 0 && (
                          <div className="cs-qa-sources">
                            <span className="cs-qa-sources-label">
                              {t("qaSection.sources", "Sources:")}
                            </span>
                            <div className="cs-qa-source-list">
                              {msg.sources.map((src, i) => (
                                <span key={i} className="cs-qa-source-chip">
                                  {getSourceTypeIcon(src.type)}&nbsp;{getSourceLabel(src)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                    </div>
                  ))}

                  {/* Typing indicator */}
                  {isLoading && (
                    <div className="cs-qa-message cs-qa-message--assistant">
                      <div className="cs-qa-bubble cs-qa-bubble--typing">
                        <span className="cs-qa-dot" />
                        <span className="cs-qa-dot" />
                        <span className="cs-qa-dot" />
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {/* ── Input area ── */}
                <div className="cs-qa-input-row">
                  <textarea
                    ref={textareaRef}
                    className="cs-qa-textarea"
                    placeholder={t("qaSection.inputPlaceholder", "Ask a question about your content…")}
                    value={input}
                    onChange={(e) => {
                      if (e.target.value.length <= MAX_QUESTION_LENGTH) {
                        setInput(e.target.value);
                      }
                    }}
                    onKeyDown={handleKeyDown}
                    maxLength={MAX_QUESTION_LENGTH}
                    rows={2}
                    disabled={isLoading}
                  />
                  <button
                    className={`cs-qa-send-btn ${canSend ? "cs-qa-send-btn--active" : ""}`}
                    onClick={handleSend}
                    disabled={!canSend}
                    title={t("qaSection.send", "Send (Enter)")}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M22 2L11 13"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M22 2L15 22L11 13L2 9L22 2Z"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>
                <div className="cs-qa-input-hint">
                  {t("qaSection.enterHint", "Enter to send · Shift+Enter for new line")}
                </div>
              </>
            )}
    </div>
  );
};

export default QASection;
