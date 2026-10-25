# Delivering as a courier

## How do I find errands to deliver?

Switch to Courier Mode and open "Open Orders". It lists requests that are open
and have not reached their deadline, with the supplier, items, delivery location
and deadline for each. You can filter by location or supplier.

## How do I accept an errand?

In Courier Mode, open "Open Orders" and click "Accept Order" on the request you
want. It then appears under "Active Assignment".

## Why did I get an error when accepting an order?

Accepting fails when someone else accepted the order first, the order was
cancelled, its deadline has passed, it is your own request, or you are not in
Courier Mode. Only one courier can be assigned to each order, so if two couriers
accept at the same moment, only the first succeeds. The list refreshes
automatically, so the order will disappear shortly.

## Can I accept more than one errand at a time?

<!-- REVIEW: The backlog (F4.3.1) says a courier with an active assignment cannot
accept another order, but the code does not enforce this yet
(order_queries.assign_courier). Write the answer once the team decides. -->

FoC shows your current errand under "Active Assignment". Finish your current
errand before taking on another one.

## What are the steps after I accept an errand?

1. Collect the items from the supplier, then click "Mark Picked Up".
2. Deliver the items to the requester's delivery location, then click "Mark
   Delivered".
3. Wait for the requester to confirm receipt. You are paid the reward credit
   after they confirm.

You must do these steps in order.

## When do I get paid for an errand?

You receive the reward credit after you mark the errand delivered and the
requester confirms receipt. The credit arrives a moment after confirmation;
until then the errand shows that credit processing is pending.

## How many credits do I earn per errand?

Each errand currently pays 1 credit.

<!-- REVIEW: Tied to the hard-coded 1-credit reward; see credits.md. -->

## Can I cancel an errand after accepting it?

No. Once you accept an errand, only you can progress it, and there is currently
no option to hand it back. Only accept errands you can complete.

<!-- REVIEW: No courier un-assign or dispute flow exists. Update if one is added. -->

## Do I pay for the items?

FoC does not handle payment for the items themselves: paying the store is
outside the platform. Credits are only the reward for completing the errand.

<!-- REVIEW: Confirm the team's guidance on how requesters and couriers settle
item payment (e.g. pay on delivery) and add it here. -->

## Can I see the requester's contact details?

No. Orders identify the requester only by a short ID such as "Student 6aac8e5f".
Their name, email, phone number and Telegram handle are not shown.

<!-- REVIEW: The frontend builds "Student <first 8 chars of user ID>"
(api/orders.js:62). Update if display names or contact details are shown to the
assigned courier, or when chat (N2H2) is built. -->
