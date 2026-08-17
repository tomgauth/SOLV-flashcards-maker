# SOLV Funnel Lab

A GERU-style **visual funnel simulator** — MVP. One self-contained HTML file, no build step, no dependencies.

Open `index.html` in a browser (double-click, or `python3 -m http.server` and browse to it).

## What it does

- **Visual, linear funnel board**: a traffic source followed by any number of steps (pages), connected left-to-right by the flow of leads.
- Each connector carries an **editable conversion rate**; each card shows **how many people reach/complete that step per month** and, for sales steps, monthly revenue.
- **Traffic source**: monthly visitors × cost per click → ad spend.
- **Sales steps** have a price; several sales steps in a row model an upsell (its rate applies to the buyers of the previous step).
- **Summary sidebar** (GERU-style): products & revenue, traffic, expenses (ad spend, merchant fee %, delivery cost per sale, fixed costs), and KPIs — profit, ROAS, EPC, CPL, CAC, AOV.
- **⚗ Simulate**: 1,000 Monte-Carlo months. Every step has a min–max range (see "Simulation range" on each card); each run samples rates from a triangular distribution and moves people through binomial draws. You get P10 / median / P90 for profit, revenue and sales, the % of profitable months, a profit histogram, and a per-step P10–P90 range under each card.
- Add / move / delete steps, templates, EUR/USD/GBP, autosave to localStorage, JSON export/import.

## Default numbers

The **SOLV Languages** template is prefilled from the "Main Funnel Numbers" page of the SOLV Languages 30-90 doc (weekly averages of the YT Ads funnel): CPC ≈ €0.65, landing conversion ≈ 9.5%, webinar show-up ≈ 75%, call show-up ≈ 70%, close ≈ 25%, ≈ €2,000 per sale. Simulation ranges come from the "Typical Numbers" table.

## Model semantics

- The chain is linear: `people(step i) = people(step i−1) × rate(i)`. Deterministic numbers are expected values (hence fractional sales like 1.9/mo).
- `CPL` = ad spend ÷ output of the first step after traffic. `CAC` = ad spend ÷ buyers of the first sales step. `AOV` = total revenue ÷ those buyers. `EPC` = revenue ÷ clicks.
- Editing anything invalidates the last simulation (stale results are cleared).

## Roadmap ideas

- Branches (email follow-up sequences, retargeting loops) and merge nodes.
- Multiple traffic sources feeding one funnel.
- Scenario compare (A/B side by side), saved scenarios.
- Goal-seek ("what landing conversion do I need for €10k/mo?").
