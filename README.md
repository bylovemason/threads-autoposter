# Threads auto-poster (@bylovemason)

> LinkedIn poster lives in the `linkedin/` folder of this same repo. Setup: [linkedin/README.md](linkedin/README.md).

Free. Posts to Threads through Meta's official API, from GitHub's free servers, even when your laptop is off.

## How it works

- `queue.json` holds the posts waiting to go out, top one first.
- `config.json` sets the posting times, the timezone, and a pause switch.
- Every hour, GitHub runs `post.py`. If a posting time is due, it publishes the top post and moves it to `posted.json`.
- Every Monday, a second job renews your Threads token, so it never expires.

## Setup (about 30 minutes, once)

### 1. Create a GitHub account
Go to github.com and sign up (free).

### 2. Create a private repository
1. Click **+** (top right) > **New repository**.
2. Name: `threads-autoposter`.
3. Choose **Private**.
4. Tick **Add a README file**.
5. Click **Create repository**.

Then tell Claude your GitHub username. Claude uploads all the files for you.

(Doing it yourself instead: see "Manual upload" at the bottom.)

### 3. Get a long-lived Threads token
If you already converted your token to the 60-day one, skip this.

1. developers.facebook.com > Tools > Graph API Explorer > switch to threads.net > select your app > **Generate Threads Access Token**. Copy it.
2. In your app dashboard, copy the **Threads app secret**.
3. In a private browser window, open (replace the two capital parts):
   `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=YOUR_APP_SECRET&access_token=YOUR_SHORT_TOKEN`
4. Copy the `access_token` value from the result. That's your 60-day token.

### 4. Add the token as a secret
In your repository: **Settings > Secrets and variables > Actions > New repository secret**.
- Name: `THREADS_TOKEN`
- Secret: paste the 60-day token
- Click **Add secret**

Secrets are hidden. Nobody can read them, including you, once saved.

### 5. Let the poster save its progress
**Settings > Actions > General > Workflow permissions** > choose **Read and write permissions** > **Save**.

### 6. Let the token renew itself
1. Click your profile picture > **Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token**.
2. Name: `threads-token-refresh`. Expiration: 1 year.
3. Repository access: **Only select repositories** > `threads-autoposter`.
4. Permissions > Repository permissions > **Secrets: Read and write**.
5. Generate, copy it.
6. Back in the repository: **Settings > Secrets and variables > Actions > New repository secret**. Name: `GH_PAT`, Secret: paste it.

### 7. Test it
1. Go to the **Actions** tab. If asked, click **I understand my workflows, enable them**.
2. Click **Post to Threads** > **Run workflow** > type `yes` in the box > **Run workflow**.
3. About a minute later, the test post is on your Threads. Delete it from Threads afterwards.
4. Then click **Refresh Threads token** > **Run workflow**. A green tick means renewal works.

Done. It now runs on its own.

## Day to day

- **New posts:** Claude writes the batch, you approve it in chat, and Claude adds them to `queue.json`. Or edit `queue.json` yourself on github.com (pencil icon).
- **Change posting times:** edit `post_times` in `config.json`. Times are in the `timezone` set there.
- **Pause everything:** set `"paused": true` in `config.json`.
- **Something failed:** GitHub emails you. Most failures are an expired token: redo steps 3 and 4.

## Manual upload (only if you don't want Claude to upload)

On a Mac, the `.github` folder is hidden in Finder, so create those two files by hand:
1. In the repo, **Add file > Upload files**, drag in `post.py`, `config.json`, `queue.json`, `posted.json`, `README.md`, commit.
2. **Add file > Create new file**, name it `.github/workflows/post.yml`, paste the contents of that file, commit.
3. Same again for `.github/workflows/refresh-token.yml`.
