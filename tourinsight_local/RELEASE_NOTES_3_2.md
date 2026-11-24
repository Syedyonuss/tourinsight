# TourInsight 3.2 — Editorial Neo-Brutalist Experience

This release is a visual and motion refinement of TourInsight 3.1. It preserves the existing pages, application data, navigation targets, and backend workflows.

## Design direction
- Editorial travel storytelling inspired by premium travel publications and award-recognized interactive websites.
- Natural but bold palette: deep forest, warm paper, butter yellow, leaf green, dusty coral and muted sky.
- Space Grotesk for display typography, Fraunces for editorial emphasis, and DM Sans for readable interface text.
- Strong neo-brutalist outlines and offset shadows, balanced with more deliberate whitespace and restrained surface styling.

## Motion
- Refined page and hero entrance choreography.
- Scroll-direction-aware reveal transitions.
- Staggered service-card entrances.
- Low-amplitude hero-image parallax.
- Pointer-following light on service tiles.
- Tactile button and card feedback.
- `prefers-reduced-motion` support remains enabled.

## Install — complete package
1. Extract the ZIP into a normal folder.
2. Install Python 3.10+ and enable Add Python to PATH.
3. Run `run_windows.bat`.
4. Open the exact localhost URL printed in the terminal.

## Install — frontend patch
Copy the contents of `tourinsight_local/web/` into the matching `web/` folder of your existing project, allowing the updated `index.html`, `assets/app.css`, `assets/app.js`, and new `assets/experience-v32.css` to be copied. Keep your existing `database/` and `web/uploads/` data.

## Validation
- Python compilation checked.
- Browser JavaScript syntax checked with Node.
- Backend smoke suite: 34/34 passed.
- A full visual browser QA pass has not been performed in this build environment.
