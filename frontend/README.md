# Conflux HQ frontend

Next.js application with React, Tailwind, and Recharts. All frontend source, assets, package manifests, and configuration live in this directory.

## Run locally

From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000.

```sh
npm run build
npm start
npm run lint
```

Run these commands inside `frontend/`, not the repository root. For hosting, configure the application's root directory as `frontend`.

## Backend

The separate FastAPI application is in `../backend/`. Its API defaults to http://localhost:8000/api/v1, with interactive docs at http://localhost:8000/docs. See [backend setup](../backend/README.md).

The dashboard currently uses mock data; moving the application does not connect it to the backend. Never expose backend database credentials, Supabase service-role keys, or social adapter tokens to browser code.
