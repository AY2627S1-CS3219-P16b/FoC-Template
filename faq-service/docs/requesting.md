# Requesting errands

## How do I create an errand request?

Switch to Requester Mode, open "Suppliers", and click "Create Request" on the
store or facility you want items from. Enter the item description and delivery
location (both required), optional delivery instructions, and an acceptance
deadline, then submit. 1 credit is reserved as the courier's reward, and you can
track the request under "My Requests".

## Do I need to pay for the items?

Yes, before you create the request. FoC errands are collect-only: the courier
picks up and delivers your items but never pays for them. Make sure your items
are already paid for (for example, a prepaid order or online print payment) or
need no payment, such as collecting a parcel, and mention this in the item
description. Credits are only the courier's reward, not payment for the items.

## What acceptance deadlines can I choose?

You can choose "Within 30 mins", "Within 45 mins" or "Within 1 hour". The
deadline is how long couriers have to accept your request. If nobody accepts it
in time, it expires and your reserved credit is returned.

Near closing time, the deadline must end at least 10 minutes before the store
closes, so a courier still has time to get there. Options that end later are
unavailable, and the form shows when the store closes. If even 30 minutes no
longer fits, you can't create a request for that store until it next opens.

<!-- REVIEW: Options live in frontend/src/utils/deadlines.js; Order Service
enforces the 60-minute maximum and the 10-minute closing buffer
(order_queries.py). Update if scheduled errands (N1) or custom deadlines are
added. -->

## How do I tell the courier where to deliver?

Type your delivery location in the "Delivery Location" field when you create the
request. Be specific so the courier can find you, for example "COM3 Level 1,
outside the lift lobby". Use "Delivery Instructions" for anything extra, such as
"leave it at the reception counter". The courier sees both on the order.

## Why does my request say "Credit processing is pending"?

FoC is reserving the reward credit for your request. This usually takes about a
second, after which the request becomes open to couriers. If it stays pending
longer, credit processing is temporarily delayed; FoC retries automatically and
updates the request on its own, so you don't need to submit it again.

If the retries keep failing, FoC stops retrying and the request shows "Credit
processing needs admin attention". It stays pending until an admin retries the
credit processing. No credits are lost or charged twice while it waits.

## When can couriers see my request?

Only after your reward credit has been reserved. Once that happens, the request
becomes open and appears under "Open Orders" for couriers until someone accepts
it or the deadline passes.

## What do the request statuses mean?

- **Pending (credit processing)**: the reward credit is being reserved, returned
  or paid. The request updates automatically. A needs-admin-attention warning
  means credit processing has stopped until an admin resolves it.
- **Open**: waiting for a courier to accept it.
- **Accepted**: a courier has taken your errand. If the courier gives it back
  before pickup, it returns to Open for another courier.
- **Picked up**: the courier has collected your items.
- **Delivered**: the courier says the items were delivered. Please confirm receipt.
- **Completed**: receipt was confirmed and the courier has been paid.
- **Cancelled**: you cancelled the request; your credit was returned.
- **Expired**: nobody accepted it before the deadline; your credit was returned.
- **Rejected**: you did not have enough credits to reserve the reward.

## Can I cancel my request?

Yes, while it is still open and no courier has accepted it. Click "Cancel
Request" under "My Requests". Your reserved credit is returned a moment later.
Once a courier has accepted the request, it can no longer be cancelled. If the
courier gives it back before pickup, it is open again and you can cancel it.

<!-- REVIEW: No cancellation or dispute flow exists after acceptance. Update if
the team adds one (e.g. N1 failed-order/dispute management). -->

## Can I edit my request after creating it?

No. To change the items, delivery location or deadline, cancel the request
while it is still open and create a new one. Your reserved credit is returned a
moment after cancelling. Once a courier has accepted your request, it can no
longer be cancelled or changed.

## What happens if nobody accepts my request?

When the acceptance deadline passes, the request expires automatically and your
reserved credit is returned to your available balance. You can create a new
request at any time.

## How do I confirm I received my items?

When the courier marks your errand as delivered, a "Confirm Delivery" button
appears on the request under "My Requests". Clicking it queues the courier's
reward transfer; the errand completes when that transfer succeeds.

Delivered requests show the automatic confirmation deadline in My Requests.
Receipt is confirmed automatically after the configured window (24 hours after
delivery by default), and the courier's reward transfer is queued. Confirm
receipt yourself once you have the items.


## It says delivered, but I didn't receive my items. What should I do?

Do not click "Confirm Delivery" until you have your items, because confirming
completes the errand and pays the courier the reward credit. First check your
delivery location and any delivery instructions you gave, in case the courier
left the items there. Contact your courier using the preferred contact in My Requests. FoC does not
currently have a dispute process. Receipt is automatically confirmed at the
deadline shown, even if you do not confirm it yourself.

<!-- REVIEW: Dispute handling remains future work. -->

## Can I accept my own request?

No. Requesters can never accept their own requests, even in Courier Mode.

## What if I submit the same request twice by accident?

If the same submission is sent twice, for example after a double click or a
network retry, FoC creates only one request and returns it both times. Separate
requests that you create on purpose are treated as different requests.

## Can I see who is delivering my request?

After acceptance, My Requests shows your courier's display name and only their
preferred contact (Telegram, phone or email, if provided). Contact stays visible
through Delivered and is hidden once completion processing starts or the errand
ends.

## Where is my courier?

FoC does not show your courier's live location. The status under "My Requests"
shows how far along your errand is: "Accepted" means a courier has taken it and
is heading to the store, "Picked up" means they have collected your items and
are on the way to you, and "Delivered" means they say the items have arrived.
The status updates automatically as the courier progresses.

## My courier is late and my items haven't arrived. What can I do?

If your courier is taking a long time and your items still haven't arrived,
check the status under "My Requests", which updates automatically when the
courier picks up and delivers your items. Once a courier accepts your request,
FoC does not set a delivery deadline, and the request can no longer be
cancelled. Use the courier's preferred contact shown under My Requests to reach them.

## Can I reorder or schedule an errand for later?

No. Each request is created for immediate pickup with an acceptance deadline of
up to 1 hour. To request the same items again, create a new request from the
supplier's page.
