# Design Review Results: Home + Job View Pages

**Review Date**: 2026-05-18
**Routes**: `/` (Home) · `/job/:id` (Job View)
**Focus Areas**: Visual Design · UX/Usability · Responsive/Mobile · Accessibility

---

## Summary

Both pages are functionally solid but lack a cohesive visual identity — there is no persistent app header, no brand anchor, and no app-level title anywhere. The Home page buries the call to action beneath two large banners, offers no visual grouping of form steps, and has several accessibility gaps (missing fieldsets, no aria-live regions, broken link). The Job View's "done" state has no back navigation, and the loading state exposes a raw UUID with little context for users. The canvas itself (dark-themed ReactFlow) is well-executed.

---

## Issues

| # | Issue | Criticality | Category | Location |
|---|-------|-------------|----------|----------|
| 1 | No persistent app header or brand identity — no app name, logo, or navigation visible on any page | 🔴 Critical | Visual Design / UX | `src/App.tsx:7-18` |
| 2 | No page `<title>` or `<meta name="description">` — default Vite placeholder shows in browser tab and search results | 🔴 Critical | UX / Accessibility | `index.html` |
| 3 | Spoiler checkbox pre-acknowledged in code (`useState(true)`) — will ship bypassed if not changed before deploy | 🔴 Critical | UX | `src/routes/Home.tsx:30` |
| 4 | Broken `href="#"` on "sign up for the mailing list" link — scrolls to top with no action, misleads users | 🟠 High | UX / Accessibility | `src/components/SpoilerWarningBanner.tsx:17` |
| 5 | "Type" radio buttons have no `<fieldset>`/`<legend>` grouping — screen readers cannot identify the group | 🟠 High | Accessibility | `src/routes/Home.tsx:91-107` |
| 6 | Format checkboxes have no `<fieldset>`/`<legend>` grouping — screen readers cannot identify the group | 🟠 High | Accessibility | `src/components/FormatCheckboxes.tsx:21-38` |
| 7 | Dynamic search results have no `aria-live` region — screen readers are not informed when candidates appear or change | 🟠 High | Accessibility | `src/routes/Home.tsx:119-139` |
| 8 | "Done" state of Job View has no back navigation — users are trapped in canvas with no way to return to Home | 🟠 High | UX | `src/routes/JobView.tsx:29-46` |
| 9 | Two large informational banners appear before the form — users must scroll ~250px before reaching the first input | 🟡 Medium | UX / Visual Design | `src/routes/Home.tsx:83-88` · `src/components/WhatThisIsBanner.tsx` · `src/components/SpoilerWarningBanner.tsx` |
| 10 | "Search" button has no `focus-visible` ring — keyboard users cannot see focus state | 🟡 Medium | Accessibility | `src/components/TitleSearch.tsx:33-38` |
| 11 | "Generate Character Map" button has no `focus-visible` ring — keyboard users cannot see focus state | 🟡 Medium | Accessibility | `src/routes/Home.tsx:166-172` |
| 12 | "not this?" button (`text-xs`) in ResolveBanner is too small for mobile tap targets (well below 44×44 px) | 🟡 Medium | Responsive / Accessibility | `src/components/ResolveBanner.tsx:17-20` |
| 13 | `[Turnstile widget — Phase 5]` placeholder div is visible to all users — dev artifact left in production path | 🟡 Medium | Visual Design | `src/routes/Home.tsx:161-164` |
| 14 | No visual grouping of form sections — all fields flat-listed with `space-y-6`, no indication of the Search → Confirm → Configure → Generate flow | 🟡 Medium | UX / Visual Design | `src/routes/Home.tsx:82-198` |
| 15 | `HowThisWorksModal` has no focus trap — focus is not moved into modal on open, and does not return to trigger on close | 🟡 Medium | Accessibility | `src/components/HowThisWorksModal.tsx` |
| 16 | Raw Job UUID shown to users in loading state with no contextual label — not useful and looks technical/broken | 🟡 Medium | UX | `src/routes/JobView.tsx:131-133` |
| 17 | Disabled "Generate" button has no tooltip or helper text explaining what prerequisite is missing (search result, format selection) | 🟡 Medium | UX | `src/routes/Home.tsx:166-172` |
| 18 | Right sidebar in Job View is only `w-[190px]` — download button labels can overflow or truncate on some font sizes | 🟡 Medium | Visual Design / Responsive | `src/routes/JobView.tsx:36-43` |
| 19 | Dark/light mode inconsistency: Home uses system light/dark correctly, but Job View canvas and toolbar are hard-coded dark regardless of system preference | 🟡 Medium | Visual Design / Consistency | `src/routes/JobView.tsx:29-46` · `src/components/CharacterMapCanvas.tsx:148` |
| 20 | No loading/skeleton state for `recentMaps` — content appears suddenly with no transition; empty area is completely blank | ⚪ Low | UX / Visual Design | `src/routes/Home.tsx:175-197` |
| 21 | Large empty white space below the Generate button when no recent maps exist — no CTA, example maps, or placeholder | ⚪ Low | Visual Design | `src/routes/Home.tsx:175-198` |
| 22 | Radio button touch targets for "Type" are smaller than 44×44 px on mobile — difficult to tap accurately | ⚪ Low | Responsive / Accessibility | `src/routes/Home.tsx:94-105` |
| 23 | No skip-to-main-content link for keyboard users navigating with Tab | ⚪ Low | Accessibility | `src/App.tsx` / `index.html` |
| 24 | No loading tips, contextual copy, or engagement content during generation (can take ~50s) — blank waiting experience | ⚪ Low | UX | `src/routes/JobView.tsx:104-136` |
| 25 | Canvas has no accessible label or usage hint (`aria-label`) — screen readers cannot identify what the React Flow region is | ⚪ Low | Accessibility | `src/components/CharacterMapCanvas.tsx:237-254` |

---

## Criticality Legend

- 🔴 **Critical**: Breaks functionality or violates accessibility standards; fix before any public deploy
- 🟠 **High**: Significantly impacts user experience or accessibility quality
- 🟡 **Medium**: Noticeable issue that should be addressed in a near-term pass
- ⚪ **Low**: Nice-to-have improvement or minor polish

---

## Next Steps

**Immediate (before public deploy):**
1. Fix `Home.tsx:30` — reset `spoilerAcknowledged` to `false`
2. Fix `SpoilerWarningBanner.tsx:17` — replace `href="#"` with a real URL or remove the link
3. Add `<title>` and `<meta name="description">` to `index.html`
4. Create a shared `AppHeader` component and add it to `App.tsx` — also adds the "Done" back navigation naturally via the logo link

**Accessibility pass (High priority):**
5. Wrap "Type" radios in `<fieldset><legend>Type</legend>…</fieldset>`
6. Wrap `FormatCheckboxes` checkboxes in `<fieldset><legend>…</legend></fieldset>`
7. Add `aria-live="polite"` to the resolve-result area in `Home.tsx`
8. Add `focus-visible:ring-2 focus-visible:ring-blue-500` to the Search and Generate buttons
9. Implement focus trap in `HowThisWorksModal` (move focus on open, return on close)

**UX improvements (Medium priority):**
10. Hide or conditionally render the Turnstile placeholder div until Phase 5 is complete
11. Add visual step grouping (cards or dividers) to the Home form flow
12. Expand the Job View right sidebar to ~240px and add job metadata + Share/Export buttons
13. De-emphasize Job ID — put it inside a `<details>` element
14. Add a tooltip or helper text to the disabled Generate button

**Polish (Low priority):**
15. Add loading skeleton or empty-state illustration for the recent maps area
16. Add `LoadingTips` component with contextual content during map generation
17. Add `aria-label="Character map canvas"` to the ReactFlow container
18. Add a skip-to-main-content link to `index.html`
