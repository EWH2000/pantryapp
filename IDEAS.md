# Ideas & Friction

A running log for pantryapp — things we want to add (**Ideas**) and rough
edges noticed while actually using it (**Friction**). Capture freely here;
promote items into a real plan/build when we pick them up. Newest notes on
top within each section. Dates are when the note was added.

---

## Ideas

### Expiration date on items — *2026-05-30*

Add an optional "use by" date to each item.

- **Model:** new `expires_on: date | None` on `Item` (optional — most
  pantry staples don't need one).
- **Entry:** use the native HTML `<input type="date">` so the iPad shows
  its built-in date wheel — no custom picker, touch-friendly for free.
- **Display ideas:** show the date on the item; color or badge items that
  are **expiring soon / expired** (e.g. amber within 3 days, red past due),
  independent of the stock-status color. Maybe a sort/filter "expiring
  soon" view.
- **Open question:** does expiry drive its own indicator, or fold into the
  existing left-edge color? Leaning toward a *separate* small badge so
  "running low" and "about to expire" stay distinguishable.

### Adjustable quantity with auto-low color — *2026-05-30*

Let the actual number go up and down, and let the color follow it.
(Directly addresses the friction note below.)

- **Quantity steppers:** big `−` / `+` buttons on each item to draw the
  count down as you use things (e.g. ground beef 6 → 5 → 4 lbs), instead
  of only flipping to Low/Out by hand. Touch targets ≥44px like the rest.
- **Auto color from a threshold:** to compute "below ~33%" we need a
  baseline to measure against — the current `quantity` alone has no notion
  of "full." Option A: add a `par` / `full_quantity` field (the amount you
  consider fully stocked) and derive status as a % of par. Option B:
  remember the highest quantity seen as "full." Leaning **A** — explicit
  par is predictable and lets the partner set "we keep 6 lbs."
- **Status interaction:** if color becomes automatic (ok/low/out derived
  from quantity vs. par), do we keep the manual Have it/Low/Out buttons?
  Likely keep a manual **override** (some things you just *know* are low),
  but default to auto. Decide when we build it.
- **Thresholds:** start simple — `out` at 0, `low` below ~33% of par,
  else `ok`. Make the 33% a single constant so it's easy to tune.

---

## Friction

### Can't decrement a count — only mark Low/Out — *2026-05-30*

Real example: added **ground beef, 6, lbs**. As we use it there's no way
to knock the number down to 5, 4, … — the only stock controls are the
Have it / Low / Out buttons, which don't reflect *how much* is left. Want
to adjust the actual quantity, and ideally have the color react to it.
→ Tracked as the **Adjustable quantity** idea above.

---

## Cross-cutting notes

### Schema changes need a migration story — *2026-05-30*

Both ideas above add a column to the `Item` table (`expires_on`, and
maybe `par`). We currently create tables with SQLModel's
`create_all()`, which **only creates missing tables — it does NOT alter
existing ones**. While the pantry is empty/dev we can just delete
`pantry.db` and let it recreate. But once there's real data on the
kitchen iPad, adding a field needs a deliberate migration (a manual
`ALTER TABLE`, or adopting a tool like Alembic). Flagging so a future
field-add doesn't silently fail to apply to the live database.
