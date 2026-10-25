# Account and admin

## How do I update my profile?

Open "Profile". You can change your display name, contact preference, Telegram
handle, phone number and profile picture URL. Your email address cannot be
changed.

## What information is visible to other students?

Very little. In order listings, couriers see you only as a short ID such as
"Student 6aac8e5f", and requesters see their courier only as "Assigned courier".
Your display name, email address, phone number, Telegram handle and profile
picture are not shown to other students.

<!-- REVIEW: Matches api/orders.js:62-63 today. Update if names or contact
details become visible (e.g. to the assigned courier, or via chat N2H2). -->

## What does my account status mean?

An active account can use FoC normally. Admins can suspend or disable an
account; suspended or disabled accounts cannot log in.

<!-- REVIEW: Confirm the difference between SUSPENDED and DISABLED, and whether
there is an appeal or reinstatement process (N1 user-management idea). -->

## I think my account was suspended by mistake. What should I do?

Contact a FoC admin and explain the situation. Admins can review account changes
and reinstate accounts.

<!-- REVIEW: Add the real contact channel for admins. -->

## What can admins do?

Admins can do everything a regular student can, plus: view and update user
accounts, change account status, promote other students to admin or demote
them, view all orders, and manage the supplier list. Every admin change to a
user's profile, status or role is recorded in an audit log.

## How do I become an admin?

An existing admin must promote your account. The very first admin is set up
once by the team that runs FoC.

## Can I delete my account?

Account deletion is not currently available.

<!-- REVIEW: No deletion endpoint exists. Confirm the team's position (e.g. ask
an admin to disable the account) and update. -->
