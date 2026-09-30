# Data

`generate_data.py` produces the six source tables for Brindle Fiber, a made-up fiber ISP,
as CSV files in `csv/`. The files are committed, so you can skip running the script. Run
it anyway once, because reading its header is part of BF-11.

```bash
python data/generate_data.py          # rewrite csv/ and print a profile of the data
python data/generate_data.py --check  # confirm csv/ matches the generator exactly
```

## Why it is built this way

- **Standard library only, seeded with 42.** Faker's output changes between releases, so a
  Faker seed does not guarantee the same data on someone else's laptop. Plain `random`
  does. Any Python 3.9 or newer produces byte-identical files.
- **Exact planted counts.** Blanks, future dates and orphans are sampled to exact numbers
  (the `N_*` constants), not probabilities, so every count in the backlog is an assertion.
- **Blanks are empty unquoted fields.** A blank is written as `,,`. There are no NULLs in
  the source. If there were, they would be written as `\N`. That convention is what lets
  the Postgres and Snowflake loads keep `''` and NULL apart.

## What the profile should print

```
passings    16374   (= 18253 - 1442 blank - 437 not yet in service)
subscribers 1316
penetration 8.04%
```

The full profile, including the by-market split and the defect A numbers, matches
[`../docs/BUSINESS_RULES.md`](../docs/BUSINESS_RULES.md).

`export_seed_sql.py` writes `snowflake/raw/seed_network.sql` from these CSVs. That file
is the BF-71 path: the same rows, inserted with SQL, with no stage. Re-run it if you
regenerate the network data.

## The NetSuite data (optional track)

`generate_netsuite.py` writes six more tables into `csv/netsuite/`: vendor bills and
payments shaped like a Fivetran NetSuite extract. It reads the network build from
`generate_data.py`, so every location built produces construction, materials and
engineering bills for its service area. Same rules: standard library only, seeded (with
4242), exact planted counts, Decimal for money.

```bash
python data/generate_netsuite.py          # rewrite csv/netsuite/ and print a profile
python data/generate_netsuite.py --check  # confirm csv/netsuite/ matches the generator
```

The profile should open its anchor section with:

```
total capex paid     $23,287,443
unknown market       $589,924  (2.53%)
capex per passing    $1,422  (all capex / 16,374 passings)
```

Change the network data and the NetSuite data changes with it, so regenerate both.

## Changing the data

You can, as a stretch exercise. Change a constant, regenerate, and every anchor number in
the docs moves with it. Confirm your measures are still correct **before** you look at the
new numbers, and never tune the data to make a wrong measure look right.
