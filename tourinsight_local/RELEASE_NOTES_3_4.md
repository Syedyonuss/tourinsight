# TourInsight 3.4 — Considered Travel Edition

## Visual direction
- Replaced the high-saturation, high-contrast 3.3 layer with a restrained palette: warm ivory, soft stone, sage, muted clay and deep forest.
- Reduced heavy outlines, hard offset shadows, decorative gradients and excessive motion.
- Refined navigation, typography, card surfaces, spacing, buttons and responsive layouts.
- Added a travel-editorial field guide with large destination photography and calmer information hierarchy.

## New user-facing experience: Stays & experiences
- Community-mentioned accommodation leads for Hampi, Gokarna, Sakleshpur and the Netravati / Chikkamagaluru region.
- Activity discovery for kayaking, coastal walks, Netravati trekking, jeep safaris, waterfalls and heritage visits.
- First-hand traveller field notes summarising trip budgets, accommodation issues, logistics, seasonality and caveats.
- Destination, travel-style and sorting filters; local shortlist saved in the browser; map, booking-search and Reddit links.
- Direct links to the underlying Reddit threads and a fresh Reddit search for the selected destination.
- A practical pre-booking checklist covering location, recent reviews, full price, season/safety and booking terms.

## Trust and data boundaries
- Reddit content is summarised and attributed with links; TourInsight does not claim these are verified reviews or endorsements.
- Historical prices are labelled as traveller-reported, not current offers. No live price, availability or star-rating claims are made.
- Booking links open search results rather than implying a confirmed reservation or direct property partnership.
- Google Maps links open live place searches; no Google Maps review text is copied or stored.
- Community recommendations are a curated sample, not a comprehensive or continuously synchronised Reddit feed.

## Preserved
- Existing FastAPI / SQLite backend and all prior TourInsight features.
- Destination explorer, SmartSeason, trip planner, community, toolkit, analytics, sentiment, forecasting, data quality and admin functions.

## Verification
- JavaScript syntax checks passed.
- Python compile checks passed.
- Existing smoke suite: 34/34 passed.
- Browser visual QA could not be completed in this environment because a Playwright browser binary was not installed.
