# Mosaic frontend

Next.js App Router application using TypeScript, ESLint, and Tailwind CSS.

## Development

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000.

## Checks

Run from `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

## Application files

- `src/app/page.tsx`: homepage.
- `src/app/layout.tsx`: shared layout and page metadata.
- `src/app/globals.css`: global styles and Tailwind imports.
- `src/styles/tokens.css`: shared colors, spacing, and corner radii.
