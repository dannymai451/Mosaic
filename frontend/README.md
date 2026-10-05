# Mosaic frontend

Next.js App Router application using TypeScript, ESLint, and Tailwind CSS.

## Development

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000 to match the backend's current credentialed CORS origin.

## Checks

The standard full-project check runs from the repository root:

```bash
uv run --project backend --locked python scripts/verify.py
```

See [root README](../README.md) for prerequisites and
[feature map](../docs/FEATURE_MAP.md) for current routes and manual checks.

Run from `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

`typecheck` generates Next.js route types before running TypeScript, including
the global `LayoutProps` used by the root layout.

## Application files

- `src/app/page.tsx`: homepage.
- `src/app/layout.tsx`: shared layout and page metadata.
- `src/app/globals.css`: global styles and Tailwind imports.
- `src/styles/tokens.css`: shared colors, spacing, and corner radii.
