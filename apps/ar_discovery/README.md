# A&R Discovery Report Generator

Produces the weekly A&R scout report across 4 detection passes (velocity outliers,
sonic shifts, geographic breakout, cobrand crossover). Pure Python, stdlib only.

---

## Quick start (with real data)

```bash
cd apps/ar_discovery
python3 ar_report.py --data-dir /path/to/your/real_data --output report.md
```

The script expects 7 files in `--data-dir`. File names are fixed (see below).

---

## Data sources & credentials

### 1. Chartmetric — `chartmetric_rising.json`

**What it is:** Artist list filtered to your target genres, <100K monthly listeners,
>20% MoM growth. Also provides city-level fanbase concentration (used in Detection 3).

**How to get it:**
- Log in at chartmetric.com → API section → generate a personal API token
- Endpoint: `GET /artist/list` with filters `genre`, `spotify_monthly_listeners_max=100000`
- Pull `fanbase_city` breakdown from `GET /artist/{id}/where-people-listen`

**Credential:**
```
# .env
CHARTMETRIC_TOKEN=your_token_here
```

**Shape expected by the script** (one entry per artist):
```json
{
  "artist": "Artist Name",
  "genre": "Phonk",
  "spotify_monthly_listeners": 61200,
  "mom_growth_rate_current": 0.54,
  "mom_growth_rate_prior": 0.31,
  "genre_median_growth": 0.21,
  "label": null,
  "spotify_url": "https://open.spotify.com/artist/REAL_ID",
  "city_top": "Atlanta, GA",
  "city_top_pct": 38.1,
  "city_top_pct_60d_ago": 44.7
}
```

`genre_median_growth` is the Chartmetric-reported genre-wide MoM median —
pull it from `GET /genre/spotify/listeners` or compute it from the full genre cohort
before filtering to the <100K artists.

---

### 2. TikTok chart movers — `tiktok_chart_movers.json`

**What it is:** Tracks with fastest-growing TikTok sound use count WoW.

**How to get it (two options):**

**Option A — Chartmetric TikTok endpoint (easiest):**
- `GET /track/tiktok/trending` — returns sound use counts and WoW delta
- Same Chartmetric token as above

**Option B — TikTok Research API (requires application approval):**
- Apply at developers.tiktok.com → Research API
- `GET /research/video/query` with sound_id filters

**Shape expected:**
```json
{
  "track": "Artist Name - Track Title",
  "artist": "Artist Name",
  "sound_use_count_this_week": 284000,
  "sound_use_count_last_week": 91000,
  "wow_growth": 2.12,
  "genre": "Phonk"
}
```

---

### 3. Cobrand affinity — `cobrand_affinity.json`

**What it is:** Audience affinity index scores by brand category, keyed by artist name.

**How to get it:**
- This is a Chartmetric Pro feature: `GET /artist/{id}/audience-affinity`
- Alternatively, export from your existing Cobrand/Nielsen/MRI-Simmons seat

**Shape expected** (artist name as key):
```json
{
  "Artist Name": {
    "fast_food": 1.82,
    "streaming_video": 1.61,
    "major_sportswear": 1.74
  }
}
```

Threshold for Detection 4 flag is `>1.5×` (configurable in `detections.py:COBRAND_THRESHOLD`).

---

### 4. Spotify audio features — `spotify_audio_features.json`

**What it is:** Audio features for the top 20 new releases this week vs. 12-month
genre averages. Drives Detection 2 sonic shift analysis.

**How to get it:**
- Spotify Web API — no special tier required, standard OAuth client credentials
- `GET /audio-features?ids=track_id1,track_id2,...`
- `GET /audio-analysis/{id}` for tempo

**Credential:**
```
# .env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Get credentials at: developer.spotify.com → Dashboard → Create App → Client ID/Secret.
Auth flow: Client Credentials (no user login needed).

**Shape expected:**
```json
{
  "genre_12mo_averages": {
    "Phonk": { "tempo": 138.2, "energy": 0.79, ... }
  },
  "top_20_new_releases_last_4wk": [
    { "title": "...", "genre": "Phonk", "tempo": 151.0, "energy": 0.85, ... }
  ]
}
```

The 12-month averages are not returned by Spotify directly — compute them by
averaging Spotify audio features across your tracked genre cohort over the prior 12 months.

---

### 5. Reddit posts — `reddit_posts.txt`

**What it is:** Top 15 posts from r/hiphopheads, r/indieheads, r/popheads.
Used in Detection 3 for geographic corroboration.

**How to get it:**

**Option A — Reddit API (PRAW):**
```
pip install praw
```
```
# .env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=ar-scout-bot/1.0
```
Get credentials at: reddit.com/prefs/apps → Create App (script type).

**Option B — Manual paste:** Paste text of top 15 posts from each subreddit.
The script does plain-text search — no structured format required.

**Shape expected:** Free-form text file. Artist names and subreddit names like
`r/houston`, `r/losangeles` etc. are matched via substring search.

---

### 6. Shazam movers — `shazam_movers.csv`

**What it is:** Top Shazam movers by WoW growth rate this week.

**How to get it:**
- Shazam does not have a public API. Options:
  - **Chartmetric** exposes Shazam chart data: `GET /chart/shazam/track`
  - **Apple Music for Artists** dashboard (if you have label access) includes Shazam data
  - **Manual export** from the Shazam for Artists portal

**Shape expected:**
```
rank,artist,track,shazam_count_this_week,shazam_count_last_week,wow_growth_pct,genre
1,Artist Name,Track Title,48200,14100,241.8,Phonk
```

---

### 7. TikTok trending sounds — `tiktok_trending.txt`

**What it is:** Manually curated list of trending TikTok sounds with creation counts.

**How to get it:**
- Open TikTok Creative Center → Trending → Sounds (sorted by weekly growth)
- Paste the top sounds with creation count and genre manually
- Or pull from Chartmetric TikTok endpoint (same as source 2)

**Shape expected:** Free-form text. Script does plain-text search against this file.

---

## Environment variables summary

Create a `.env` file (not committed to git):

```bash
# Chartmetric (covers sources 1, 2, 3, 6)
CHARTMETRIC_TOKEN=

# Spotify Web API (source 4)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=

# Reddit PRAW (source 5) — optional, can paste manually
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ar-scout-bot/1.0
```

---

## Fictional sample data

`sample_data_FICTIONAL/` contains structurally correct but entirely invented
artist names and metrics. Use it to test the pipeline and validate output format.
**Do not use it for actual A&R decisions.**

The file `weekly_ar_report_2026-03-06_FICTIONAL_DATA.md` was generated from
that fictional data and is included only to demonstrate report format.

---

## Adjusting detection thresholds

All thresholds are constants at the top of `detections.py`:

| Constant | Default | Detection |
|---|---|---|
| `COBRAND_THRESHOLD` | `1.5` | D4 — minimum affinity index for cobrand flag |
| `>2 * median` (inline) | `2×` | D1 — velocity outlier multiplier |
| `>40` / `>5pp` (inline) | 40% / 5pp | D3 — geo concentration thresholds |
| `abs(delta_pct) >= 10` (inline) | 10% | D2 — minimum sonic shift to report |
