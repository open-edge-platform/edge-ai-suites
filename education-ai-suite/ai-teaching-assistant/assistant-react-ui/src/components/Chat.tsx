import { useEffect, useRef, type ReactNode } from "react";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  partialUser?: string;
  partialAssistant?: string;
  fileName?: string;
  ingesting?: boolean;
  footer?: ReactNode;
}

export default function Chat({ messages, partialUser, partialAssistant, fileName, ingesting, footer }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, partialUser, partialAssistant]);

  const isEmpty = messages.length === 0 && !partialUser && !partialAssistant;
  const readyLabel = fileName ? `"${fileName}"` : "the uploaded file";

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-md">
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
        {isEmpty && (
          <div className="m-auto flex max-w-sm flex-col items-center gap-3 px-4 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-intel-blue text-2xl font-bold text-white shadow-lg">
              J
            </span>
            <h3 className="text-lg font-semibold text-black">
              Hi, I'm Jarvis — your AI teaching assistant
            </h3>
            <p className="text-sm text-black/60">
              {ingesting ? (
                "Ingesting your document\u2026"
              ) : fileName ? (
                <>
                  Ask me anything about {readyLabel}.
                  <br />
                  Speak with the mic or type your question below.
                </>
              ) : (
                "Upload your course material, then ask me anything about it — by voice or text."
              )}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <Bubble key={i} role={m.role} text={m.text} />
        ))}
        {partialUser && <Bubble role="user" text={partialUser} partial />}
        {partialAssistant && <Bubble role="assistant" text={partialAssistant} partial />}
        <div ref={endRef} />
      </div>
      {footer && <div className="mt-3">{footer}</div>}
    </div>
  );
}

function Bubble({
  role,
  text,
  partial,
}: {
  role: "user" | "assistant";
  text: string;
  partial?: boolean;
}) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2 text-sm ${
          isUser
            ? "bg-intel-blue text-white"
            : "border border-blue-200 bg-white text-black"
        } ${partial ? "opacity-70" : ""}`}
      >
        {text}
        {partial && <span className="ml-0.5 animate-pulse">▌</span>}
      </div>
    </div>
  );
}
