# Getting started

## What is Friend on Campus (FoC)?

Friend on Campus is a peer-to-peer errand platform for NUS students. A student
who needs something collected from a campus store or facility posts an errand
request, and another student picks it up and delivers it. The person who
delivers earns the credits the requester offered as a reward.

## Who can use FoC?

FoC is for NUS students. You need an NUS student email address in the format
`<nusid>@u.nus.edu` to register.

## How do I create an account?

Choose "Create an account" on the login screen and enter your NUS email, a
display name and a password. Your password must be at least 10 characters long
and contain at least one uppercase letter, one lowercase letter, one digit and
one symbol. If a field is missing or invalid, the form tells you which one to
fix. Each email address can only be registered once.

## Why was my registration rejected?

Registration is rejected when the email is not an `@u.nus.edu` address, the
email is already registered, the display name is missing, or the password does
not meet the rules: at least 10 characters, with an uppercase letter, a
lowercase letter, a digit and a symbol. The error message names the field that
needs fixing.

## Why can't I log in?

Login fails when the email is not registered or the password is wrong. For
security, FoC shows the same "Invalid email or password" message in both cases.
Accounts that have been suspended or disabled by an admin also cannot log in.

<!-- REVIEW: The backlog (N1.4) plans a 15-minute lockout after 5 failed logins
within 10 minutes. This is not implemented yet. Add an answer once it is. -->

## How long do I stay logged in?

Your login session lasts 15 minutes. After that you need to log in again.

<!-- REVIEW: The code uses 15-minute access tokens with no refresh token. The
backlog (N1.2, F1.3.1) plans 30-minute access tokens plus 7-day refresh tokens
that logout invalidates. Update this answer if refresh tokens are added. -->

## How do I log out?

Click "Log out" in the top navigation bar.

## What are Requester Mode and Courier Mode?

Every student can both request and deliver errands, but you work in one mode at
a time. In Requester Mode you browse suppliers, create requests and track them
under "My Requests". In Courier Mode you browse "Open Orders", accept one and
manage it under "Active Assignment". Switch modes with the "Requester Mode" and
"Courier Mode" buttons in the navigation bar.

## Why can't I create a request or accept an order?

Creating a request requires Requester Mode, and accepting an order requires
Courier Mode. If you are in the wrong mode, FoC shows an error such as "Switch
to courier mode to accept an order." Switch modes in the navigation bar and try
again.
