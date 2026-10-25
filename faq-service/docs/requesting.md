# Requesting errands

## How do I create an errand request?

Switch to Requester Mode, open "Suppliers", and click "Create Request" on the
store or facility you want items from. Enter the item description and delivery
location (both required), optional delivery instructions, and an acceptance
deadline, then submit. 1 credit is reserved as the courier's reward, and you can
track the request under "My Requests".

## What acceptance deadlines can I choose?

You can choose "Within 30 mins", "Within 45 mins" or "Within 1 hour". The
deadline is how long couriers have to accept your request. If nobody accepts it
in time, it expires and your reserved credit is returned.

<!-- REVIEW: Options are hard-coded in CreateOrderModal.jsx:122-124 and
App.jsx:797. Update if scheduled errands (N1) or custom deadlines are added. -->

## How do I tell the courier where to deliver?

Type your delivery location in the "Delivery Location" field when you create the
request. Be specific so the courier can find you, for example "COM3 Level 1,
outside the lift lobby". Use "Delivery Instructions" for anything extra, such as
"leave it at the reception counter". The courier sees both on the order.

<!-- REVIEW: Delivery location is free text (CreateOrderModal.jsx:99-105); the
API only checks it is not empty. Update this answer if it becomes a campus place
picker (PlaceTreeSelect already exists) or saved locations (N1 bookmarking).
Couriers currently have no way to contact the requester. Consider showing the
requester's profile contact (contact preference, Telegram handle, phone) to the
assigned courier only, after acceptance, or adding chat (N2H2). Update this
answer, couriers.md and account.md if that changes. -->

## Why does my request say "Credit processing is pending"?

FoC is reserving the reward credit for your request. This usually takes about a
second, after which the request becomes open to couriers. If it stays pending
longer, credit processing is temporarily delayed; FoC retries automatically and
updates the request on its own, so you don't need to submit it again.

## When can couriers see my request?

Only after your reward credit has been reserved. Once that happens, the request
becomes open and appears under "Open Orders" for couriers until someone accepts
it or the deadline passes.

## What do the request statuses mean?

- **Pending (credit processing)**: the reward credit is being reserved, returned
  or paid. The request updates automatically.
- **Open**: waiting for a courier to accept it.
- **Accepted**: a courier has taken your errand.
- **Picked up**: the courier has collected your items.
- **Delivered**: the courier says the items were delivered. Please confirm receipt.
- **Completed**: you confirmed receipt and the courier has been paid.
- **Cancelled**: you cancelled the request; your credit was returned.
- **Expired**: nobody accepted it before the deadline; your credit was returned.
- **Rejected**: you did not have enough credits to reserve the reward.

## Can I cancel my request?

Yes, while it is still open and no courier has accepted it. Click "Cancel
Request" under "My Requests". Your reserved credit is returned a moment later.
Once a courier has accepted the request, it can no longer be cancelled.

<!-- REVIEW: No cancellation or dispute flow exists after acceptance. Update if
the team adds one (e.g. N1 failed-order/dispute management). -->

## What happens if nobody accepts my request?

When the acceptance deadline passes, the request expires automatically and your
reserved credit is returned to your available balance. You can create a new
request at any time.

## How do I confirm I received my items?

When the courier marks your errand as delivered, a "Confirm Delivery" button
appears on the request under "My Requests". Clicking it completes the errand and
pays the courier the reward credit.

## Can I accept my own request?

No. Requesters can never accept their own requests, even in Courier Mode.

## What if I submit the same request twice by accident?

If the same submission is sent twice, for example after a double click or a
network retry, FoC creates only one request and returns it both times. Separate
requests that you create on purpose are treated as different requests.

## Can I see who is delivering my request?

After a courier accepts your request, the "Courier" field under "My Requests"
changes from "Unassigned" to "Assigned courier". FoC does not currently show the
courier's name or contact details.

<!-- REVIEW: The frontend shows "Assigned courier" only (api/orders.js:63).
Update when courier names or contact details are shown, and when
requester–courier chat (N2H2) and translation (N2H3) are built. -->

## Can I reorder or schedule an errand for later?

Not yet. Each request is created for immediate pickup with an acceptance
deadline of up to 1 hour.

<!-- REVIEW: Scheduled errands and reordering are N1 ideas, not selected or
built. Remove or update this answer if the team implements them. -->
