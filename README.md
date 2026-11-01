# Threads auto-poster (@bylovemason)

Posts to Threads through Meta's official API from GitHub's free servers, even when your laptop is off.

## How it works

- `queue.json` holds upcoming posts. Each item has an `at` time (New York time) and is either a single post (`text`) or a thread (`thread`: a list of parts, posted as replies under the first one).
- Every 30 minutes between 10am and midnight New York time, GitHub runs `post.py`. Anything whose time has passed is published and moved to `posted.json`. If GitHub runs late, it catches up one extra item per run.
- Every Monday, `refresh-token.yml` renews the Threads token so it never expires.

## Settings

- `config.json`: timezone and a `paused` switch (set to `true` to stop all posting).
- Secrets (Settings > Secrets and variables > Actions): `THREADS_TOKEN` and `GH_PAT`. They are never shown in this repo.

## Run manually

Actions > Post to Threads > Run workflow > type `yes` to post the next queued item now.
