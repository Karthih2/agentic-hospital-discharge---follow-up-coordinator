# Frontend

React + Vite + Tailwind. Landing page, legal pages, and the app screens from `desgin/frontend.md`.

## Run

```bash
# 1. API (pick one)
cd backend && python -m scripts.dev_server     # in-memory data, seeded, works without Atlas/Aura. Password for all demo logins: Demo@12345
#   or: uvicorn app.main:app --port 8000        # real MongoDB + Neo4j from backend/.env

# 2. Web
cd frontend && npm install && npm run dev      # http://localhost:5173
```

On Windows with `&` in the folder path, `npm run` and `npx` can fail. Use `node node_modules/vite/bin/vite.js` and `node node_modules/typescript/bin/tsc -b` directly.

The dev server proxies the API paths in `vite.config.ts` so cookies stay same-origin. Demo logins: `patient1`, `patient2`, `patient3`, `daughter1` (runs patient1's account), `son1` (reminders), `brother1` (appointments), `doctor1` to `doctor4`, `mgmt1`. Family can also sign up on `/register` and join with a patient code.

## Where things are

| Path | What |
|---|---|
| `src/pages/Landing.tsx`, `src/pages/landing/` | Landing page. `LiveDemo.tsx` is the product demo on synthetic data |
| `src/pages/app/` | `Entry` (sign in, language, patient code), `Home` (upload, family requests), `Plan` (card and two-panel views), `Providers` (Leaflet map), `Manual`, `Staff` (doctor queue, review detail, desk), `Family` |
| `src/components/reactbits/` | React Bits SplitText, BlurText, CountUp, ScrollReveal, ScrollVelocity (copied from the registry) |
| `src/assets/icons/` | Icons sliced from `desgin/Healthcare App Icon Library.png`, background halo keyed out, upscaled 3x |
| `src/lib/i18n.tsx` | Six-language interface strings (nav, hero, buttons, footer disclaimer) |

## Rules this UI follows

No gradients, shadows, emoji, hover animation, dot grids, orbs, em dashes or lucide icons. Flat 2px navy outlines on 4px corners, the sheet's status colours, skeleton loaders for loading, footer disclaimer on every screen, provider suggestions always labelled.

## Known limits

- Icon crops are small because the source sheet is 1536x1024. Use them at about 64px or below.
- Only short interface strings are translated. Longer landing copy and app labels are English. Task text comes from the backend in the chosen language.
- Telugu, Kannada and Malayalam strings are machine translated and should be read by a fluent speaker.
- The Listen button needs `ELEVENLABS_API_KEY` and voice IDs on the backend.
