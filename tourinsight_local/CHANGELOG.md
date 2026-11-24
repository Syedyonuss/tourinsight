# TourInsight 3.0 release notes

## Visual system
- Stronger natural neo-brutalist identity: bold outlines, offset ink shadows, editorial hero composition, playful sticker treatment and pastel natural surfaces.
- Motion polish for page transitions, cards, community feed and progress bars, with reduced-motion support.
- Responsive layouts for the new community and travel-planning experiences.

## New user experiences
- District-wise destination discovery using the current catalogue's geographic pins.
- Public travel community with story, tip, question and photo-story posts.
- Secure local image uploads for community posts and photo reviews (JPG/PNG/WEBP, 5 MB limit).
- Collaborative trip groups with invite codes, shared destination suggestions and voting.
- Personal travel journal.
- Self-reported destination check-ins and travel milestone challenges.
- Shareable read-only itinerary pages.
- Transport provider shortcuts and an emergency information panel.
- English/Kannada/Hindi navigation label switching.
- Nearby destination suggestions from catalogue coordinates.
- Drag-and-drop itinerary reordering plus accessible move-up/move-down controls.

## Backend and persistence
- Added SQLite tables for community posts, journals, trip groups, group members, suggestions, votes, public itinerary tokens and destination check-ins.
- Added migration for optional review photo URL.
- Added API endpoints for all new persistent features.

## Validation
- Existing and new smoke suite: 34/34 passing.
- Python compilation and browser JavaScript syntax checks pass.


## 3.1 — Editorial experience and motion polish
- Refined the visual system with a bolder forest, butter, leaf, coral and sky palette.
- Added a service directory on the overview page linking to the existing destination, planning, community and tourism-intelligence modules.
- Added reversible scroll-reveal motion, section/page transitions, a scroll progress rail, direction-aware hide/reveal navigation and a back-to-top control.
- Added responsive service cards and reduced-motion fallbacks.

## 3.2 — World-class editorial polish
- Refined the existing natural neo-brutalist system into a more premium editorial travel experience with forest, butter, leaf, coral and warm-paper tones.
- Introduced Space Grotesk display typography with Fraunces editorial accents while retaining readable DM Sans body copy.
- Refined navigation, hero composition, service directory, cards, buttons, forms, destination imagery and footer without removing existing sections or workflows.
- Added restrained pointer-following light on service tiles and low-amplitude hero-image parallax.
- Improved scroll reveals, page entrances, staggered service-card entrances and tactile button/card feedback.
- Retained reduced-motion fallbacks and responsive layouts.

## 3.3 — Colour-forward visual refresh
- Replaced muted earth-tone direction with a vivid, coordinated palette: plum, sunset coral, electric lilac, sky blue, citrus yellow and fresh lime.
- Added richer gradient hero, multicolour service hub, vibrant KPI cards, colourful destination cards, stronger contrast and bolder navigation.
- Preserved all existing pages, data, controls, and application behavior.

## 3.4 — Considered Travel Edition
- Shifted the interface to a subtle editorial palette and removed the loud 3.3 colour treatment.
- Added the Stays & Experiences field guide with community-sourced accommodation/activity leads, Reddit field notes, shortlist, filters and pre-booking checks.
- Preserved all existing application features and data.

## 3.5 — Trust-first discovery and comparison
- Added a reported-amount filter to the Stays & Experiences field guide; unknown amounts remain visible and traveller-reported units are explicitly not treated as directly comparable.
- Added a compare tray for up to three stays or activities, with side-by-side location, price evidence, source date, traveller context and caveats.
- Added direct independent-check shortcuts for recent review searches, Maps location checks and Tripadvisor searches.
- Comparison intentionally avoids invented star ratings or opaque composite scores; each source remains linked to its original discussion.
- Preserved the existing curated content, backend and user data.
