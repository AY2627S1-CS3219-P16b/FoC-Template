# Credits

## What are credits?

Credits are FoC's reward currency. Requesters offer credits as a reward for an
errand, and couriers earn them by completing errands. Credits only exist inside
FoC: they cannot be bought, withdrawn or exchanged for money, and they are not
used to pay the store for your items.

## How many credits do I start with?

Every new account receives 20 credits. They are added automatically shortly
after you register.

<!-- REVIEW: 20 comes from INITIAL_CREDITS in compose.yaml. Update this answer
if the team changes the value. -->

## I just registered. Why don't I see my credits yet?

Your starting credits are added in the background a moment after registration,
so they can take a few seconds to appear. If Credit Service is temporarily
unavailable, FoC keeps retrying and the credits appear once it is back. You will
only ever receive your starting credits once.

## How do I check my credit balance?

Your available credits are shown in the navigation bar. The "Credits" page shows
your available credits, credits currently reserved for your open requests, and
a history of every credit change.

## What is the difference between available and reserved credits?

Available credits are yours to spend on new requests. Reserved credits are held
for a request you have already created: they leave your available balance, but
they are not paid to anyone until the errand is completed. If the request is
cancelled or expires, reserved credits return to your available balance.

## How much does a request cost?

Each request currently offers a reward of 1 credit. The credit is reserved from
your available balance when you create the request.

<!-- REVIEW: The frontend hard-codes a 1-credit reward (CreateOrderModal.jsx:47),
while the Order API accepts any positive amount. Update this answer if requesters
can choose the reward. -->

## When are my credits taken?

When you create a request, 1 credit moves from your available balance to
reserved. It is only paid to the courier after the courier marks the errand
delivered and you confirm that you received it.

## When does the courier get paid?

The courier receives the reserved credit after they mark the errand delivered
and the requester confirms receipt. The transfer happens a moment after
confirmation; until then the request shows that credit processing is pending.

## What happens to my credits if my request is cancelled or expires?

Your reserved credit is returned to your available balance. This happens a
moment after the cancellation or expiry; until then the request shows that
credit processing is pending.

## Why was my request rejected?

A request is rejected when you do not have enough available credits to reserve
its reward. Check your balance on the "Credits" page before creating another
request. No credits are taken for a rejected request.

## Can I be charged twice or lose credits if something fails?

No. Every credit operation is recorded with a unique key, so if a step is
retried after a failure, it is applied only once. Your available balance can
never go below zero, and the same credits cannot be spent twice.

## Can I buy, transfer or withdraw credits?

No. Credits can only be earned by completing errands or received as your
starting allocation. You cannot buy them, send them to another student directly,
or exchange them for money.
