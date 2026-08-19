import { useEffect, useRef, type ReactNode } from "react";
import type { ChatMessage } from "../types";

interface Props {
  messages: ChatMessage[];
  partialUser?: string;
  partialAssistant?: string;
  fileName?: string;
  footer?: ReactNode;
}

export default function Chat({ messages, partialUser, partialAssistant, fileName, footer }: Props) {
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
          <div className="m-auto text-sm italic text-black/60">
            {fileName
              ? `Tap the mic and ask a question about ${readyLabel}.`
              : "Upload a file to start asking questions about it."}
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
