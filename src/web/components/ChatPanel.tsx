"use client";

// The whole chat: message list, pill input bar, attach button, send.
// The customer can attach an image, a video, or an invoice (pdf/txt) -
// the backend reads it with OCR and uses the text in its answer.
import { useEffect, useRef, useState } from "react";
import { getSessionId } from "../lib/session";
import TraceCard, { Trace } from "./TraceCard";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// What the customer attached, kept for display. The preview URL is a
// local object URL (URL.createObjectURL) - the file never leaves the
// browser for display purposes; the backend only gets it for OCR.
type AttachmentView = { url: string; name: string; isImage: boolean; isVideo: boolean };

// One entry in the chat, in display order: a customer bubble, a bot
// answer, or a small italic note about what the OCR read.
type Item =
  | { kind: "customer"; text: string; attachment?: AttachmentView }
  | { kind: "bot"; text: string; sources: string; handoff: boolean }
  | { kind: "note"; text: string };

type ChatResponse = {
  answer: string;
  status: string;
  trace: Trace;
  attachment_note?: string | null;
};

// The backend answer ends with a "Sources:" line - split it off so the
// answer stays clean text and the sources get their own subtle styling.
function splitSources(answer: string): { text: string; sources: string } {
  const marker = "\nSources:";
  const i = answer.indexOf(marker);
  if (i === -1) return { text: answer, sources: "" };
  return { text: answer.slice(0, i), sources: answer.slice(i + 1).trim() };
}

export default function ChatPanel() {
  const [items, setItems] = useState<Item[]>([]);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // Staged-attachment preview shown above the input bar before sending.
  const [preview, setPreview] = useState<AttachmentView | null>(null);
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const chatEnd = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Keep the newest message in view.
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [items]);

  // Close the attach menu when clicking anywhere else or pressing Escape.
  useEffect(() => {
    if (!menuOpen) return;
    function close(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function esc(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [menuOpen]);

  // Stage (or unstage) the picked file and its preview. The object URL is
  // revoked when the file is removed without sending; on send, ownership of
  // the URL passes to the message bubble, so it is NOT revoked here.
  function stageFile(f: File | null) {
    if (preview) URL.revokeObjectURL(preview.url);
    setFile(f);
    setPreview(
      f
        ? {
            url: URL.createObjectURL(f),
            name: f.name,
            isImage: f.type.startsWith("image/"),
            isVideo: f.type.startsWith("video/"),
          }
        : null
    );
  }

  async function send() {
    const text = input.trim();
    if ((!text && !file) || busy) return;
    setBusy(true);
    const shown = text || "";
    // Show the attachment inside the bubble, reusing the staged preview:
    // a real thumbnail for images, a file chip for everything else.
    const attachment: AttachmentView | undefined = preview || undefined;
    setItems((it) => [...it, { kind: "customer", text: shown, attachment }]);
    setInput("");

    const form = new FormData();
    form.append("session_id", getSessionId());
    form.append("message", text);
    if (file) form.append("file", file);
    // Clear the staging area WITHOUT revoking the URL - the bubble owns it now.
    setFile(null);
    setPreview(null);
    if (fileInput.current) fileInput.current.value = "";

    try {
      const resp = await fetch(`${API}/api/chat`, { method: "POST", body: form });
      const body: ChatResponse = await resp.json();
      if (!resp.ok) throw new Error((body as any).detail || "request failed");
      const { text: answerText, sources } = splitSources(body.answer);
      setItems((it) => {
        const next: Item[] = [...it];
        if (body.attachment_note) {
          next.push({ kind: "note", text: `Attachment: ${body.attachment_note}` });
        }
        next.push({
          kind: "bot",
          text: answerText,
          sources,
          handoff: body.status === "handoff",
        });
        return next;
      });
      setTrace(body.trace);
    } catch (err: any) {
      setItems((it) => [...it, {
        kind: "bot", text: `Something went wrong: ${err.message}`,
        sources: "", handoff: false,
      }]);
    }
    setBusy(false);
  }

  async function talkToHuman() {
    const resp = await fetch(`${API}/api/handoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId() }),
    });
    const body: ChatResponse = await resp.json();
    const { text: answerText, sources } = splitSources(body.answer);
    setItems((it) => [...it, { kind: "bot", text: answerText, sources, handoff: true }]);
    setTrace(body.trace);
  }

  return (
    <>
      <div className="chat">
        {items.length === 0 && (
          <div className="empty">
            Ask something - e.g. &quot;How long does shipping take?&quot; - or
            tap + to attach an invoice or photo and ask about it.
          </div>
        )}
        {items.map((item, i) => {
          if (item.kind === "customer") {
            return (
              <div key={i} className="msg-customer">
                {item.attachment &&
                  (item.attachment.isImage ? (
                    <a href={item.attachment.url} target="_blank" rel="noreferrer"
                       title="Open full size">
                      <img className="attachment-thumb"
                           src={item.attachment.url}
                           alt={item.attachment.name} />
                    </a>
                  ) : (
                    <span className="file-attachment">
                      <span className="file-attachment-icon">
                        {item.attachment.isVideo ? "🎬" : "📄"}
                      </span>
                      <span className="file-attachment-name">{item.attachment.name}</span>
                    </span>
                  ))}
                {item.text && <span>{item.text}</span>}
              </div>
            );
          }
          if (item.kind === "note") {
            return <div key={i} className="note">{item.text}</div>;
          }
          return (
            <div key={i} style={{ alignSelf: "flex-start", maxWidth: "92%" }}>
              {item.handoff && <div className="state-chip">Handed to a human</div>}
              <div className="msg-bot">
                {item.text}
                {item.sources && <div className="sources">{item.sources}</div>}
              </div>
            </div>
          );
        })}
        <div ref={chatEnd} />
      </div>

      <div className="composer-wrap">
        {preview && (
          <div className="staged-preview">
            {preview.isImage ? (
              <img className="staged-thumb" src={preview.url} alt={preview.name} />
            ) : (
              <span className="file-attachment staged-chip">
                <span className="file-attachment-icon">
                  {preview.isVideo ? "🎬" : "📄"}
                </span>
                <span className="file-attachment-name">{preview.name}</span>
              </span>
            )}
            <button
              className="staged-remove"
              title="Remove attachment"
              onClick={() => stageFile(null)}
            >
              ×
            </button>
          </div>
        )}
        <div className="composer">
          <input
            ref={fileInput}
            type="file"
            accept="image/*,video/*,.pdf,.txt,.md"
            style={{ display: "none" }}
            onChange={(e) => stageFile(e.target.files?.[0] || null)}
          />
          <div className="attach-menu-wrap" ref={menuRef}>
            {menuOpen && (
              <div className="attach-menu">
                <button
                  className="attach-menu-item"
                  onClick={() => {
                    setMenuOpen(false);
                    fileInput.current?.click();
                  }}
                >
                  <span className="attach-menu-icon">📎</span>
                  <span className="attach-menu-text">
                    <span className="attach-menu-title">Add photos &amp; files</span>
                    <span className="attach-menu-sub">Upload from computer</span>
                  </span>
                </button>
              </div>
            )}
            <button
              className="icon-btn"
              title="Attach an image, video, or invoice"
              onClick={() => setMenuOpen((open) => !open)}
            >
              +
            </button>
          </div>
          <input
            type="text"
            placeholder="Ask anything"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="send-btn" onClick={send} disabled={busy}>
            {busy ? "..." : "Send"}
          </button>
        </div>
        <button className="human-btn" onClick={talkToHuman}>
          Not solved? Talk to a human
        </button>
      </div>

      <TraceCard trace={trace} />
    </>
  );
}
