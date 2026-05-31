# Ideas & Friction

A running log for pantryapp — things we want to add (**Ideas**) and rough
edges noticed while actually using it (**Friction**). Capture freely here;
promote items into a real plan/build when we pick them up. Newest notes on
top within each section. Dates are when the note was added.

---

## Ideas

### Recipes + "can I make it?" cross-check — *2026-05-31* — *v2 / larger*

The v2 "meal ideas" direction, fleshed out. Two connected pieces:

1. **Recipes in the app.** Add/edit a recipe as a **checklist** of
   ingredients — name, and (optionally) how much. The checklist doubles as
   a cook-along: tick ingredients off as you use them.
2. **Cross-check against the pantry.** For each recipe, compare its
   ingredients to what's on hand and show a clear **"you can make this"** /
   **"missing X, Y"** verdict. Ideally browse recipes filtered to "makeable
   right now."

- **New data model (the v2 second model):** `Recipe` + `RecipeIngredient`
  (one recipe, many ingredients). This is the recipes / ingredient-matching
  model CLAUDE.md's scope calls out as deliberately out of v1.
- **The hard part — matching ingredients to pantry items:** a recipe says
  "ground beef"; the pantry has an `Item` named "Ground Beef." Options:
  fuzzy name match (normalize case/whitespace), or link each ingredient to a
  specific `Item` via a picker (more reliable, more setup). Lean toward
  name-match first, manual link as an upgrade.
- **Presence vs. enough:** start simple — do we *have* the ingredient at all
  (status not `out` / quantity > 0)? A later upgrade checks we have *enough*,
  which means comparing required amount to on-hand amount, and unit
  conversion (lbs vs oz vs "2 onions") is genuinely messy. Presence first;
  quantity-sufficiency is a follow-up.
- **Ties into other ideas:** ticking ingredients off while cooking could
  **decrement pantry quantities** (see *Adjustable quantity*), and the
  makeable/not verdict is only as good as the `status`/quantity data.
- **Touch UX:** "what can we make?" should be a big, glanceable list on the
  kitchen display — green = make it now, with any missing items spelled out.

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
  baseline ("full") to measure against — the current `quantity` alone has
  no notion of it. **Decided (2026-05-30):** "full" = **the quantity first
  entered** when the item is created. Store it as a `par` / `full_quantity`
  field, but **auto-seed it from the initial quantity** so there's no extra
  input — add ground beef at 6 lbs and par becomes 6. Keep the field
  editable later (you can correct "we actually keep 8"). Status is then a %
  of par. *(See the learned-restock idea below for making par smarter over
  time.)*
- **Status interaction:** if color becomes automatic (ok/low/out derived
  from quantity vs. par), do we keep the manual Have it/Low/Out buttons?
  Likely keep a manual **override** (some things you just *know* are low),
  but default to auto. Decide when we build it.
- **Thresholds:** start simple — `out` at 0, `low` below ~33% of par,
  else `ok`. Make the 33% a single constant so it's easy to tune.

### Learned restock amount — *2026-05-30* — *fuzzy / later*

Captured early; details TBD. If we tend to **buy the same amount each
time**, the app should notice and default to it — so "full" / par isn't
just the first entry forever, it adapts to how we actually restock.

- **Sketch:** when an item is restocked (quantity bumped back up, or marked
  Have-it after being Out), record *how much* it was topped up to. Over a
  few cycles, if that amount is consistent, treat it as the item's natural
  "full" and use it for par / the restock default.
- **Why it's nice:** par stops being a guess from one moment; the +/-
  steppers and the low threshold reflect real buying habits. Buy milk a gal
  at a time → "full" settles on 1 gal even if you once entered 2.
- **Unknowns (on purpose):** how many cycles before trusting a pattern?
  median vs. last-value vs. mode? what if the amount drifts (switched pack
  size)? Manual override always wins. No need to solve now — just don't
  lose the idea.
- **Dependency:** needs a little history per item (restock events), so
  it's downstream of the basic quantity/par work above, not part of it.

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
