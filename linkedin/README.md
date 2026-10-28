# LinkedIn auto-poster (Love Mason)

Free. Posts to Love Mason's personal LinkedIn profile through LinkedIn's official API, from GitHub's free servers, even when your laptop is off. Lives in the same repo as the Threads poster, so GitHub access and permissions are already set up.

## How it works

- `linkedin/queue.json` holds the posts waiting to go out. Each one has its own `"at"` time (New York time).
- Every hour during US waking hours, GitHub runs `linkedin/post.py`. When a post's time has passed, it publishes it and moves it to `linkedin/posted.json`. One post per run, never a burst.
- Image posts use the black quote-card format. Claude renders the cards (`linkedin/make_card.py`) when writing the batch and commits them to `linkedin/cards/`.
- Every Monday, a check makes sure the token still works and warns you 10 days before it expires.

## Setup (about 20 minutes, once)

### 1. Create a LinkedIn developer app
1. Go to **linkedin.com/developers/apps** > **Create app**.
2. App name: `Love Mason Poster`.
3. LinkedIn Page: LinkedIn requires every app to be linked to a Page. Pick an existing one, or click **Create a new LinkedIn Page** and make a simple "Love Mason" page. Nothing gets posted there.
4. Upload any logo (your photo is fine), tick the terms, **Create app**.
5. On the **Settings** tab, click **Verify** next to the Page and follow the link (you're the Page admin, so you approve it yourself).

### 2. Turn on the two products
On the **Products** tab, click **Request access** on both:
- **Share on LinkedIn**
- **Sign In with LinkedIn using OpenID Connect**

Both are approved instantly.

On the **Auth** tab, under **Authorized redirect URLs**, add:
`https://www.linkedin.com/developers/tools/oauth/redirect`

### 3. Make a token (repeat every 60 days)
1. Go to **linkedin.com/developers/tools/oauth/token-generator**.
2. Select your app. Tick the scopes **openid**, **profile** and **w_member_social**.
3. Click **Request access token**, sign in, **Allow**.
4. Copy the access token. It lasts 60 days. LinkedIn doesn't let personal apps renew automatically, so this one step is repeated every 2 months. The Monday check emails you 10 days before it expires.

### 4. Add the token as a secret
In the `threads-autoposter` repo: **Settings > Secrets and variables > Actions > New repository secret**.
- Name: `LINKEDIN_TOKEN`
- Secret: paste the token
- **Add secret**

Then tell Claude "LinkedIn token added". Claude records today's date (for the expiry warning) and switches posting on.

### 5. Test it
1. **Actions** tab > **Post to LinkedIn** > **Run workflow** > type `yes` > **Run workflow**.
2. About a minute later the first queued post is on your LinkedIn.
3. Then **LinkedIn token check** > **Run workflow**. A green tick means the token is good.

Done. It runs on its own from here.

## Day to day

- **New posts:** Claude writes the batch, you approve it in chat, Claude pushes it to `linkedin/queue.json` with the cards.
- **Your photo on the cards:** upload a head-and-shoulders photo as `linkedin/assets/avatar.jpg` (or send it to Claude). Until then the cards show "LM".
- **Pause:** set `"paused": true` in `linkedin/config.json`.
- **Something failed:** GitHub emails you. A `401` error means the token expired: redo steps 3 and 4.
- **Version warning in the logs:** LinkedIn retires API versions about once a year. The poster steps back automatically; Claude updates `linkedin_version` in the config when you see the warning.
