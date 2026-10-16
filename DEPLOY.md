# Deploying to Render (free tier)

Everything Render needs is described in [render.yaml](render.yaml) (a Render
"Blueprint"). It creates three free resources in one region:

| Resource | Name | What it runs |
|---|---|---|
| Web Service | `stockprices-web` | gunicorn: the public site, the API, `/admin/` |
| Key Value | `stockprices-redis` | Redis: the response cache and sync locks |
| Postgres | `stockprices-db` | the database |

Database and Redis credentials are wired in automatically (`DATABASE_URL`,
`REDIS_URL`). You only type in the Massive API key and the site URL.

### What the free tier means for this app

- **No syncs on Render.** Free accounts get no background worker, so Celery
  doesn't run there and nothing syncs on a schedule. You run syncs from your
  own machine against the Render database (step 4).
- **The site sleeps** after about 15 minutes without traffic. The next visit
  waits 30–60 seconds while it wakes. That's bad for SEO, so use this setup
  for a demo or staging only.
- **The schema is applied on every boot.** The start command runs `migrate`
  and `apply_sql` first; both do nothing when nothing is pending.
- **The free Postgres database expires.** The dashboard shows its expiry
  date; upgrade before then or the data is deleted. Free Key Value keeps
  nothing across restarts, which is fine: it only holds a cache.
- **Postgres and Redis accept outside connections** (password-protected),
  because the syncs on your machine need to reach them.

---

## 1. Before you start

1. The repo must be on GitHub with `render.yaml` on `master`. It already is.
2. Have your Massive API key ready (https://massive.com/dashboard).
3. **Pick the region.** `render.yaml` uses `oregon`. To change it, edit all
   three `region:` lines and push before step 2. It cannot be changed after
   the database is created. Options: `oregon`, `ohio`, `virginia`,
   `frankfurt`, `singapore`.

## 2. Create the Blueprint

1. Go to https://dashboard.render.com → **New +** → **Blueprint** → choose the
   `stockprice` repo. (Can't see it? See "Repo not listed" under
   Troubleshooting.)
2. Render lists the three resources, each marked **Free**. If it asks for a
   card, something is still on a paid plan: check that `render.yaml` on
   GitHub is the latest version.
3. Fill in the values it asks for:

| Variable | Value |
|---|---|
| `MASSIVE_API_KEY` | your Massive key |
| `SITE_URL` | `https://stockprices-web.onrender.com` (your service's URL), no trailing slash |

   Render shows the service URL after creation. If the name was taken, it
   adds a suffix; fix `SITE_URL` afterwards under **Environment** if so.

4. Click **Apply**. The first build takes a few minutes.

## 3. Check it's up

- Web service **Logs** should show `apply_sql` listing the `sql/` files it
  applied, then gunicorn listening.
- `https://<your-host>/api/health/` should return `"status": "ok"`.
- The pages work but are empty until the first sync (next step).

## 4. Load data from your machine

Free web services have no Shell, so admin setup and syncs run locally, talking
to the Render database and Redis.

1. In the Render dashboard, copy:
   - **stockprices-db → Connections → External Database URL**
   - **stockprices-redis → Connect → External** URL (starts with `rediss://`)
   - **stockprices-web → Environment → SECRET_KEY**
2. Copy `secrets/.env.production.secrets.example` to
   `secrets/.env.production.secrets` (git ignores it) and fill in
   `SECRET_KEY`, `MASSIVE_API_KEY`, `SITE_URL`, `DATABASE_URL` and `REDIS_URL`.
3. In PowerShell, from the project folder:

```powershell
$env:ENV_TYPE = "production"
.venv\Scripts\python manage.py apply_sql --list
```

   It should list every `sql/` file as applied. If so, you're talking to
   Render. Then:

```powershell
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py sync_exchanges
.venv\Scripts\python manage.py sync_stocks
.venv\Scripts\python manage.py sync_stock_details
.venv\Scripts\python manage.py refresh_sectors
.venv\Scripts\python manage.py sync_daily_prices --days 5
```

   On the free Massive tier (5 calls a minute) `sync_stock_details` takes a
   long time. Add `--limit 200` to load a sample first.

4. Each sync clears the site's cache when it finishes, so new data shows up
   straight away.

**To keep data current**, run `sync_stocks`, `sync_stock_details`,
`refresh_sectors` and `sync_daily_prices` again daily (prices after
8 pm New York time). Or, while your laptop is on, run Celery locally with the
same environment and it follows the schedule in `app/config/celery.py`:

```powershell
$env:ENV_TYPE = "production"
.venv\Scripts\celery -A app worker -B --pool=solo --loglevel=info
```

Close that PowerShell window (or clear `$env:ENV_TYPE`) before going back to
local development, or your commands will keep hitting the Render database.

## 5. Optional

- **Custom domain:** **stockprices-web → Settings → Custom Domains**, add the
  DNS records it shows, then set `SITE_URL` to the new URL, and add
  `ALLOWED_HOSTS` (`www.example.com`) and `CSRF_TRUSTED_ORIGINS`
  (`https://www.example.com`) under **Environment**. The `onrender.com` host is
  always allowed. Update `SITE_URL` in your local secrets file too.
- **Other settings** (`INDEXNOW_KEY`, `SITE_TWITTER`, `ORGANIZATION_SAME_AS`):
  add them under **Environment**. See `.env.example`.

## Day-to-day

- **Deploy:** push to `master`. Render rebuilds, and the new schema (any new
  `.sql` file) is applied when it boots. A failing `.sql` file stops the boot
  and the old version keeps serving.
- **Changed an API response?** Run `clear_api_cache` locally with
  `$env:ENV_TYPE = "production"`.
- **Logs:** the web service's **Logs** tab.

## Moving to paid

When this becomes the real site, change `render.yaml`:

1. Remove `plan: free` from all three resources (Render then uses its
   smallest paid size), and set `ipAllowList: []` on Postgres and Key Value
   to close outside access.
2. Move `migrate` and `apply_sql` from `startCommand` into
   `preDeployCommand`, so a broken schema stops the deploy before it goes live.
3. Add a worker that runs the scheduled syncs, with the same env vars as the
   web service and `PROJECT_NAME` identical (it names the Celery queue):

```yaml
  - type: worker
    name: stockprices-worker
    runtime: python
    region: oregon
    branch: master
    buildCommand: pip install -r requirements/prod.txt
    startCommand: celery -A app worker -B --loglevel=info --concurrency=2
```

   Keep it at exactly one instance; beat runs inside it.

The free Postgres can be upgraded in place from its dashboard page, which
keeps the data.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Repo not listed in the Blueprint picker | Render's GitHub app can't see it: github.com/settings/installations → Render → Configure → add `stockprice`. |
| Render asks for a card | A resource isn't on `plan: free`. Push the latest `render.yaml`. |
| `400 Bad Request` on a custom domain | Add it to `ALLOWED_HOSTS`. |
| `403 CSRF verification failed` on the admin login | Add `https://` + that domain to `CSRF_TRUSTED_ORIGINS`. |
| Health check fails | `/api/health/` returns 503: check that the database and Key Value are up and in the same region. |
| Local sync says a table doesn't exist | `ENV_TYPE` isn't `production` in that window, so it hit your local database. |
| Site still shows old data after a local sync | `REDIS_URL` in your secrets file isn't the Render one, so the cache clear went to your local Redis. |
| Canonical URLs show the wrong host | `SITE_URL` is wrong on Render. Fix it, then run `clear_api_cache`. |
