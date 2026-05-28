# Backdrop maps

The geographic view at `/geo/:jobId` loads `westeros.jpg` from this
directory as its backdrop. Drop your Westeros / Known World map here as
`westeros.jpg` before generating the GoT special map.

Notes:
- The region anchors in `frontend/src/geographic/westeros.ts` assume the
  Adam Whitehead "Known World" 2014 map layout (Westeros on the left third,
  Essos sweeping right). Anchors are fractional (0–1) so any image with
  that rough layout will work; you can fine-tune the fractions if a
  particular region ends up in the wrong spot.
- The view sizes the image to `min(2400px, 100%)` so a high-res source
  scales cleanly on desktop.
- For personal use only — this map is fan-made and copyrighted; do not
  commit it to the public repo.
