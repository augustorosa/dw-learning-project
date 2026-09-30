# Brindle Fiber

Brindle Fiber is a made-up fiber internet provider. Six markets, a network build, and a
billing system that had a bad month in 2022. Every company, vendor, and address in this
repo is synthetic. The numbers are consistent with each other. They are not a real ISP.

This page is the operating story. The rules and the anchor numbers live in
[`BUSINESS_RULES.md`](BUSINESS_RULES.md). If the two ever disagree, the business rules
win.

## How a home gets on the report

A market is a city Brindle builds in. Hubsites feed service areas, and service areas feed
PON zones. A PON zone is the piece of network that can light a street. A location is one
home or business on that street.

When construction finishes, the location gets an in-service date. From that date it is a
**passing**: an address the network can serve today. Some locations in the extract have a
blank date. They are on the map and not in service. Some have a real date after the
report date. They are scheduled and not in service yet. Neither one is a passing.

A customer shows up as an order, and an address can have more than one. An order was
either installed or cancelled. The report does not want orders. It wants addresses that
have ever been installed, counted once, from the first day that happened.

## The month the billing system lied

In March 2022 a billing migration cancelled a batch of installed orders. Those customers
signed again over the following months. By 13 September 2024 every one of them was back,
so a report that only checks that date looks perfect.

The months in between are the damage. A rule that asks "what is this address's latest
order, and is it active?" drops those customers for the whole gap, then welcomes them
back at the end. The September page still reads 1,316 subscribers. March 2022 does not.
That is the bug the project is built around.

## The page leadership actually reads

Once a month, leadership reads **Cohort Performance By Market**. Six rows. Three numbers.
Passings, subscribers, and penetration, as at a report date. For this project the date is
**2024-09-13**.

Penetration is the company's subscribers divided by the company's passings. It is not the
average of the six market rates. A small market and a large market are not the same vote.

## The question finance asks later

Finance wants a second number, and it is optional here: what did each home passed cost to
build? The spend is not in the network database. It is in the ERP, as vendor bills and
the payments that settled them. Bills have lines. Payments pay bills, not lines. Some
money has no market, because someone left the service area blank.

The homes are in the network data. The dollars are in the ERP. They meet at the market,
or they do not meet at all.

## What you receive each night

The operational database is restored from backup every night. The restore throws away
change history. You do not get a stream of what changed. You get a full copy of the
tables, once a day, blanks and bad types included. Anything you need to remember, you
keep yourself.

## Where to go next

Read [`BUSINESS_RULES.md`](BUSINESS_RULES.md), then [`SETUP.md`](SETUP.md), then start at
**BF-01**.
