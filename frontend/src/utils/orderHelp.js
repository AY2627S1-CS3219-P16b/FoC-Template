import { shortOrderId, statusLabel } from "./orderPresentation.js";

// Each question matches an FAQ heading in faq-service/docs, so the Help
// assistant retrieves the right answer. Only these generic questions are sent
// to the FAQ service: order details never leave the browser.
const Q = {
  pending: 'Why does my request say "Credit processing is pending"?',
  whenVisible: "When can couriers see my request?",
  cancel: "Can I cancel my request?",
  edit: "Can I edit my request after creating it?",
  noAccept: "What happens if nobody accepts my request?",
  whereCourier: "Where is my courier?",
  whoCourier: "Can I see who is delivering my request?",
  tooLong: "My courier is late and my items haven't arrived. What can I do?",
  confirm: "How do I confirm I received my items?",
  notReceived: "It says delivered, but I didn't receive my items. What should I do?",
  courierPaid: "When does the courier get paid?",
  balance: "How do I check my credit balance?",
  refund: "What happens to my credits if my request is cancelled or expires?",
  rejected: "Why was my request rejected?",
  steps: "What are the steps after I accept an errand?",
  courierCancel: "Can I cancel an errand after accepting it?",
  payItems: "Do I pay for the items?",
  requesterContact: "Can I see the requester's contact details?",
  getPaid: "When do I get paid for an errand?",
  earn: "How many credits do I earn per errand?",
};

const REQUESTER_HELP = {
  RESERVING: ["We're reserving 1 credit for your request. It opens to couriers in a moment.", [Q.pending, Q.whenVisible]],
  OPEN: ["Waiting for a courier to accept your request before the acceptance deadline.", [Q.cancel, Q.edit, Q.noAccept]],
  ACCEPTED: ["A courier has taken your errand and is heading to the store.", [Q.whereCourier, Q.whoCourier, Q.cancel]],
  PICKED_UP: ["Your courier has collected your items and is on the way to you.", [Q.whereCourier, Q.tooLong]],
  DELIVERED: ["Your courier says your items were delivered. Confirm receipt once you have them.", [Q.confirm, Q.notReceived]],
  COMPLETING: ["You confirmed receipt. The courier's reward is being processed.", [Q.courierPaid, Q.pending]],
  COMPLETED: ["This errand is complete and the courier has been paid.", [Q.courierPaid, Q.balance]],
  CANCELLING: ["Your request is being cancelled. Your credit will be returned in a moment.", [Q.refund, Q.pending]],
  CANCELLED: ["You cancelled this request and your credit was returned.", [Q.refund, Q.balance]],
  EXPIRING: ["No courier accepted before the deadline. Your credit will be returned in a moment.", [Q.noAccept, Q.refund]],
  EXPIRED: ["No courier accepted before the deadline, so your credit was returned.", [Q.noAccept, Q.refund]],
  REJECTED: ["You didn't have enough available credits to reserve the reward.", [Q.rejected, Q.balance]],
};

const COURIER_HELP = {
  ACCEPTED: ["Collect the items from the supplier, then mark them picked up.", [Q.steps, Q.payItems, Q.courierCancel]],
  PICKED_UP: ["Deliver the items to the requester, then mark them delivered.", [Q.steps, Q.requesterContact]],
  DELIVERED: ["Waiting for receipt confirmation. Automatic confirmation applies at the displayed deadline.", [Q.getPaid, Q.earn]],
  COMPLETING: ["The requester confirmed receipt. Your reward is being processed.", [Q.getPaid]],
  COMPLETED: ["Errand complete. Your reward has been paid.", [Q.getPaid, Q.balance]],
};

const FALLBACK = ["Ask anything about this errand.", [Q.steps, Q.getPaid]];

/** Status-specific summary and FAQ questions for one of the viewer's orders. */
export function orderHelpTopics(status, role) {
  const table = role === "courier" ? COURIER_HELP : REQUESTER_HELP;
  const [summary, questions] = table[status]
    || (role === "courier" ? FALLBACK : ["Ask anything about this request.", [Q.pending, Q.cancel]]);
  return { summary, questions };
}

/** The local context shown in the Help panel; never sent to the FAQ service. */
export function orderHelpContext(order, role) {
  return {
    orderId: order.id,
    name: order.supplierName || "Order",
    title: `${order.supplierName || "Order"} · #${shortOrderId(order.id)}`,
    statusLabel: statusLabel(order.status),
    ...orderHelpTopics(order.status, role),
  };
}

export const ORDER_HELP_EVENT = "foc:order-help";

const FINISHED = ["COMPLETED", "CANCELLED", "EXPIRED", "REJECTED"];

/** The viewer's own unfinished requests plus their courier assignment, for Help. */
export function helpOrderChoices(orders, userId) {
  const requests = orders
    .filter((order) => order.requesterId === userId && !FINISHED.includes(order.status))
    .map((order) => ({ order, role: "requester" }));
  const deliveries = orders
    .filter((order) => order.courierId === userId && !FINISHED.includes(order.status))
    .map((order) => ({ order, role: "courier" }));
  return [...requests, ...deliveries];
}

// The App publishes the current choices; the Help panel (mounted outside App)
// subscribes. Logging out reloads the page, which clears the list.
let choices = [];
const listeners = new Set();

export function publishHelpOrders(next) {
  choices = next;
  listeners.forEach((listener) => listener(choices));
}

export function subscribeHelpOrders(listener) {
  listeners.add(listener);
  listener(choices);
  return () => listeners.delete(listener);
}

/** Open the Help panel with its general suggestions. */
export function openHelp() {
  window.dispatchEvent(new CustomEvent(ORDER_HELP_EVENT, { detail: null }));
}

/** Open the Help panel with suggestions for this order. */
export function openOrderHelp(order, role) {
  window.dispatchEvent(new CustomEvent(ORDER_HELP_EVENT, { detail: orderHelpContext(order, role) }));
}
