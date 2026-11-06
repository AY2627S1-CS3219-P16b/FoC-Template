import React, { useEffect, useRef, useState } from "react";
import { askFaq } from "../api/faq";
import { ORDER_HELP_EVENT, orderHelpContext, subscribeHelpOrders } from "../utils/orderHelp";
import { statusLabel } from "../utils/orderPresentation";
import "./FaqSupport.css";

const SUGGESTIONS = ["How do I create an account?", "How do credits work?", "Can I cancel my request?"];

export default function FaqSupport() {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  // Conversation entries: "user" and "assistant" messages, plus local-only
  // "order" cards and "menu" lists, so they appear where the user is looking.
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  // The signed-in user's active orders, published by App; empty when logged out.
  const [orderChoices, setOrderChoices] = useState([]);
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

  const addEntry = (entry) => setMessages((previous) => [
    ...previous.slice(-39), { id: crypto.randomUUID(), ...entry },
  ]);

  const showOrder = (context) => setMessages((previous) => {
    const last = previous[previous.length - 1];
    if (last?.role === "order" && last.context.orderId === context.orderId) return previous;
    return [...previous.slice(-39), { id: crypto.randomUUID(), role: "order", context }];
  });

  useEffect(() => {
    // A "Get help" link sends an order; the navbar Help button sends null.
    const openHelp = (event) => {
      if (event.detail) showOrder(event.detail);
      setOpen(true);
    };
    window.addEventListener(ORDER_HELP_EVENT, openHelp);
    return () => window.removeEventListener(ORDER_HELP_EVENT, openHelp);
  }, []);

  useEffect(() => subscribeHelpOrders(setOrderChoices), []);

  // Show each order's current status as App refreshes orders.
  const liveContext = (context) => {
    const choice = orderChoices.find(({ order }) => order.id === context.orderId);
    return choice ? orderHelpContext(choice.order, choice.role) : context;
  };
  const lastMenuOrOrder = [...messages].reverse().find(({ role }) => role === "order" || role === "menu");
  const currentOrder = lastMenuOrOrder?.role === "order" ? liveContext(lastMenuOrOrder.context) : null;

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
    addEntry({ role: "user", text });
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

  const suggestionButtons = (questions) => (
    <div className="faq-suggestions">
      {questions.map((text) => (
        <button key={text} type="button" onClick={() => submit(null, text)} disabled={pending}>{text}</button>
      ))}
    </div>
  );

  const helpMenu = (key) => (
    <div key={key} className="faq-welcome">
      {orderChoices.length > 0 && (
        <div className="faq-order-choices">
          <p>Need help with an order?</p>
          <ul>
            {orderChoices.map(({ order, role }) => (
              <li key={order.id}>
                <button type="button" onClick={() => showOrder(orderHelpContext(order, role))}>
                  <span>
                    <strong>{order.supplierName || "Order"}</strong>
                    <small>{role === "courier" ? "Your delivery" : "Your request"}</small>
                  </span>
                  <span className="faq-order-status">{statusLabel(order.status)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p>{orderChoices.length > 0 ? "Or ask a general question" : "How can I help?"}</p>
      {suggestionButtons(SUGGESTIONS)}
    </div>
  );

  const orderCard = (entry) => {
    const context = liveContext(entry.context);
    return (
      <div key={entry.id} className="faq-order-context" aria-label={`Help for ${context.name}`}>
        <div className="faq-order-heading">
          <strong>{context.title}</strong>
          <span className="faq-order-status">{context.statusLabel}</span>
        </div>
        <p>{context.summary}</p>
        {suggestionButtons(context.questions)}
        <small>Order details aren't shared with the AI.</small>
      </div>
    );
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
            AI answers from our FAQ. Don’t share passwords or personal details.
          </p>
          {currentOrder && (
            // Outside the scrolling transcript, so switching stays in reach.
            <div className="faq-order-bar">
              <span>Helping with <strong>{currentOrder.name}</strong></span>
              <button type="button" onClick={() => messages[messages.length - 1]?.role !== "menu" && addEntry({ role: "menu" })}>Other help</button>
            </div>
          )}
          <div className="faq-transcript" role="log" aria-label="Support conversation" aria-live="polite" aria-relevant="additions">
            {messages.length === 0 && helpMenu("welcome")}
            {messages.map((message) => {
              if (message.role === "menu") return helpMenu(message.id);
              if (message.role === "order") return orderCard(message);
              return (
                <article key={message.id} className={`faq-message faq-message-${message.role}`}>
                  <span className="faq-speaker">{message.role === "user" ? "You" : "FoC Help"}</span>
                  <p>{message.text}</p>
                  {message.sources?.length > 0 && (
                    <details className="faq-sources">
                      <summary>Based on {message.sources.length} FAQ {message.sources.length === 1 ? "answer" : "answers"}</summary>
                      {message.sources.map((source) => (
                        <div key={source.id} className="faq-source">
                          <strong>{source.question}</strong>
                          <p>{source.answer}</p>
                        </div>
                      ))}
                    </details>
                  )}
                </article>
              );
            })}
            {pending && <p className="faq-pending" role="status">Finding an answer…</p>}
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
