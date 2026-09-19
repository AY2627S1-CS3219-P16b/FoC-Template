# Start Friend on Campus locally

Run the user service and frontend in separate terminals from the repository
root.

## Terminal 1: user service

```bash
cd user-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:create_app --factory --env-file .env.dev --reload --port 8000
```

On a fresh checkout, create `user-service/.env.dev` with these settings:

```dotenv
DATABASE_URL=sqlite:///data/users.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_SECRET=replace-with-a-long-random-local-secret
```

Replace the secret before starting. This file is ignored by Git. All three
variables are required; the service fails at startup when any is missing.

The API is at `http://localhost:8000`; interactive documentation is at
`http://localhost:8000/docs`.

## Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to the user
service on port 8000. Unauthenticated visitors see the landing page; direct
registration and login routes are `?screen=register` and `?screen=login`.

For a remotely hosted API, set `VITE_USER_API_URL` to its origin before
starting or building the frontend.
