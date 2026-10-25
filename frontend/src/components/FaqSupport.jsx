import React, { useEffect, useRef, useState } from "react";
import { askFaq } from "../api/faq";
import "./FaqSupport.css";

const SUGGESTIONS = ["How do I create an account?", "How do credits work?", "Can I cancel my request?"];

export default function FaqSupport() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const launcherRef = useRef(null);
  const endRef = useRef(null);
  const activeRequest = useRef(null);

  useEffect(() => {
    if (open && !pending) inputRef.current?.focus();
  }, [open, pending]);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [open, messages, pending, error]);

  useEffect(() => () => activeRequest.current?.abort(), []);

  const close = () => {
    setOpen(false);
    launcherRef.current?.focus();
  };

  const submit = async (event, suggestedQuestion) => {
    event?.preventDefault();
    const text = (suggestedQuestion ?? question).trim();
    if (!text || text.length > 1500 || activeRequest.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setPending(true);
    setError(null);
    setQuestion("");
    const id = crypto.randomUUID();
    setMessages((previous) => [...previous.slice(-39), { id, role: "user", text }]);
    try {
      const result = await askFaq(text, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setMessages((previous) => [...previous, {
        id: result.request_id || crypto.randomUUID(), role: "assistant",
        text: result.answer, sources: result.sources,
      }]);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError({ message: failure.message, requestId: failure.requestId });
        setQuestion(text);
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setPending(false);
        inputRef.current?.focus();
      }
    }
  };

  const clear = () => {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setPending(false);
    setMessages([]);
    setQuestion("");
    setError(null);
    inputRef.current?.focus();
  };

  return (
    <>
      <button
        ref={launcherRef} type="button" className="faq-launcher"
        aria-expanded={open} aria-controls="faq-support-panel"
        onClick={() => open ? close() : setOpen(true)}
      >
        <span aria-hidden="true">?</span> Help
      </button>
      {open && (
        <section
          id="faq-support-panel" className="faq-panel" role="dialog"
          aria-labelledby="faq-support-title" aria-describedby="faq-support-description"
          onKeyDown={(event) => {
            if (event.key === "Escape") { event.stopPropagation(); close(); }
          }}
        >
          <header className="faq-header">
            <div>
              <h2 id="faq-support-title">FoC Help</h2>
              <p>Questions about using Friend on Campus</p>
            </div>
            <button type="button" className="faq-icon-button" aria-label="Close help" onClick={close}>×</button>
          </header>
          <p id="faq-support-description" className="faq-description">
            AI answers from our FAQ docs. Each question is answered separately.
            I can explain how FoC works, but can’t access your account or orders.
            Please don’t share passwords or personal details.
          </p>
          <div className="faq-transcript" role="log" aria-label="Support conversation" aria-live="polite" aria-relevant="additions">
            {messages.length === 0 && (
              <div className="faq-welcome">
                <p>How can I help?</p>
                <div className="faq-suggestions">
                  {SUGGESTIONS.map((text) => (
                    <button key={text} type="button" onClick={() => submit(null, text)} disabled={pending}>{text}</button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((message) => (
              <article key={message.id} className={`faq-message faq-message-${message.role}`}>
                <span className="faq-speaker">{message.role === "user" ? "You" : "FoC Help"}</span>
                <p>{message.text}</p>
                {message.sources?.length > 0 && (
                  <div className="faq-sources">
                    <span>Sources</span>
                    {message.sources.map((source) => (
                      <details key={source.id}>
                        <summary>{source.question}</summary>
                        <p>{source.answer}</p>
                        <small>{source.title}</small>
                      </details>
                    ))}
                  </div>
                )}
              </article>
            ))}
            {pending && <p className="faq-pending" role="status">Looking through the FAQs…</p>}
            <div ref={endRef} />
          </div>
          {error && (
            <div className="faq-error" role="alert">
              <p>{error.message}</p>
              {error.requestId && (
                <details key={error.requestId} className="faq-error-details">
                  <summary>Support details</summary>
                  <code>Reference: {error.requestId}</code>
                </details>
              )}
            </div>
          )}
          <form className="faq-form" onSubmit={submit} aria-busy={pending}>
            <label htmlFor="faq-question">Your question</label>
            <textarea
              ref={inputRef} id="faq-question" rows={2} maxLength={1500}
              value={question} onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about registration, errands, or credits…"
              disabled={pending}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault(); submit(event);
                }
              }}
            />
            <div className="faq-form-actions">
              <button type="submit" className="btn btn-primary" disabled={pending || !question.trim()}>
                {pending ? "Sending…" : "Send"}
              </button>
            </div>
            {(messages.length > 0 || pending) && <button type="button" className="faq-clear" onClick={clear}>Clear conversation</button>}
          </form>
        </section>
      )}
    </>
  );
}
