# Deploying DubaiPulse Analyst

Two pieces: the **backend** (FastAPI + Docker → Railway or Render) and the **frontend**
(React static build → Vercel). Deploy the backend first so you have its URL for the frontend.

> You will need: a [Anthropic API key](https://console.anthropic.com/), and free accounts on
> [Railway](https://railway.app) **or** [Render](https://render.com), plus [Vercel](https://vercel.com).

---

## Step 1 — Backend

Pick **one** host.

### Option A · Railway (CLI, fastest)

```bash
npm i -g @railway/cli
railway login                       # opens browser
cd backend
railway init                        # create a new project
railway up                          # builds the Dockerfile and deploys
```

Then set environment variables (Railway dashboard → your service → Variables, or via CLI):

```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set BACKEND_API_KEY=<a-long-random-string>
railway variables set CORS_ORIGINS=https://<your-frontend>.vercel.app
railway variables set ANTHROPIC_MODEL=claude-sonnet-5
railway domain                      # generate a public URL
```

`railway.json` (in `backend/`) already configures the Docker build and the `/health` check.

### Option B · Render (Blueprint, one click)

1. Push this repo to GitHub (see Step 0 below).
2. Render Dashboard → **New → Blueprint** → select this repo. It reads `render.yaml`.
3. When prompted, set the secret vars: `ANTHROPIC_API_KEY`, `BACKEND_API_KEY`,
   `CORS_ORIGINS` (your Vercel URL).
4. Deploy. Render builds `backend/Dockerfile` and health-checks `/health`.

### Verify the backend

```bash
curl https://<your-backend-url>/health
# → {"status":"ok","data":{"transactions":87000,"ready":true}, ...}
```

---

## Step 2 — Frontend (Vercel)

### CLI

```bash
npm i -g vercel
cd frontend
vercel                              # link/create the project (accept defaults; framework: Vite)
```

Set the environment variables (Vercel dashboard → Project → Settings → Environment Variables,
or `vercel env add`):

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://<your-backend-url>` |
| `VITE_API_KEY` | the same string you set as `BACKEND_API_KEY` on the backend |

Then deploy to production:

```bash
vercel --prod
```

`frontend/vercel.json` already sets the Vite framework, build command and SPA rewrites.

---

## Step 3 — Wire the two together

1. Copy the **Vercel production URL** and set it as `CORS_ORIGINS` on the backend
   (redeploy the backend so CORS allows the frontend origin).
2. Open the Vercel URL — the header should show **backend online** (green dot).
3. Ask a question and watch the reasoning trace stream. 🎉

---

## Step 0 — Push to GitHub (if not already)

```bash
git init && git add . && git commit -m "DubaiPulse Analyst"
git branch -M main
git remote add origin https://github.com/krish2105/Dubai-Pulse-Analyst-.git
git push -u origin main
```

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| Frontend shows **backend offline** | Check `VITE_API_BASE_URL`; confirm `/health` responds; confirm `CORS_ORIGINS` includes the exact Vercel origin. |
| `401 Missing or invalid API key` | `VITE_API_KEY` (frontend) must equal `BACKEND_API_KEY` (backend). Leave both blank to disable auth. |
| Answers come back **low-confidence / no data** | `ANTHROPIC_API_KEY` is missing or invalid on the backend — the agents can't generate SQL/prose. |
| First request is slow | Free-tier cold start; subsequent requests are fast. |
| `429 Rate limit exceeded` | Raise `RATE_LIMIT` (e.g. `60/minute`) in the backend env. |
