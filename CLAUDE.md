# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A long-running Python bot that impersonates "Patrick", a marathon-training running coach, on Reddit. It posts once daily to r/C25K, comments on fitness/running subreddits to build karma (90–110 comments/day), and organically promotes an app called "marathon100" in comments. GPT-4 generates all content.

## Running the Bot

```bash
pip install -r requirements.txt
python main.py
```

The script exits immediately if any required environment variable is missing.

## Required Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 content generation |
| `CLIENT_ID` | Reddit app client ID |
| `CLIENT_SECRET` | Reddit app client secret |
| `REFRESH_TOKEN` | Reddit OAuth refresh token |
| `USER_AGENT` | Reddit API user agent string |

## Deployment

Deployed on [Render.com](https://render.com) as a Background Worker:
- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`

## Architecture

Everything lives in `main.py` — a single-threaded polling loop. No database; all state is in-memory globals that reset on restart.

**Core flow:**
1. On startup: validates env vars, authenticates with Reddit, fetches subreddit flair info
2. Main loop runs every 60 seconds, checking three things:
   - **Posting** (checked every 15 min): if today hasn't been posted yet and UK time is 11:00–20:00, generate and submit a post to r/C25K via GPT-4
   - **Commenting** (checked every 2 min): weighted-random subreddit selection, then keyword-filter new/hot posts and reply with GPT-4 generated comment (90–110 comments/day target)
   - **Health check** (every 30 min): verifies Reddit API connection and logs status

**Key globals:**
- `patrick_state` — tracks current day number, total km, mood, struggles (used as GPT-4 context)
- `post_history` — rolling 7-day list of previous posts, injected into the generation prompt for continuity
- `last_post_date` — prevents double-posting; hardcoded to last actual post date on startup
- `commented_ids` — in-memory set of post IDs already commented on (resets on restart)
- `comment_count` / `last_comment_time` — daily comment rate limiting
- `app_mentions_today` / `app_mentions_count` — tracks daily and total "marathon100" app mentions

**Content generation:**
- Posts: GPT-4 prompt includes `patrick_state`, recent `post_history`, and time-of-day context (maps UK hour to "morning run", "lunch run", "evening run" narrative)
- Comments: subreddit-specific prompts with a `brevity_instruction` (20–80 words). High-karma subs (askreddit, nostupidquestions, lifeprotips) skip keyword filtering and target posts with `score > 10`. All other subs keyword-filter new+hot posts.

**App mention logic (`can_naturally_mention_app`):**
- Analyzes post text for tracking/app-request/plan keywords and subreddit relevance
- `adjust_app_mention_probability()` dynamically increases mention rate if behind the 30/day target
- When triggered, injects a `app_instruction` into the GPT-4 prompt asking for a casual "marathon100" mention

**Persistence (flat files):**
- `patrick_post_log.txt` — append-only log of all posts
- `comment_log.txt` — append-only log of all comments (tagged `[APP MENTION]` when applicable)
- `post_history.txt` — permanent record of post content (supplements in-memory `post_history`)

**Time handling:** All posting logic uses UK time (UTC+1 BST). `get_uk_time()` adds a fixed +1h offset — update this manually when BST/GMT changes.

## Key Configuration Constants

Located at the top of `main.py`:

- `TARGET_SUBREDDIT` — subreddit to post to (currently `"C25K"`)
- `COMMENT_SUBREDDITS` — full list of subreddits to comment on (grouped by priority in comments)
- `KEYWORDS` — keywords used to filter posts before commenting
- `MIN_DAILY_COMMENTS` / `MAX_DAILY_COMMENTS` — daily comment targets (90/110)
- `INTERVAL_BETWEEN_COMMENTS` — baseline minutes between comments (dynamically adjusted by `calculate_comment_interval`)
- `mood_cycle` — 7-entry list cycling Patrick's mood/struggles weekly

## Important Caveats

- `post_history` and `patrick_state["day"]` are hardcoded to specific values on startup — update these before redeployment to maintain continuity with prior posts
- `last_post_date` is also hardcoded; set it to the actual date of the last Reddit post before deploying
- `process_multiple_comments()` is defined but never called from the main loop (dead code)
- Comment interval is calculated dynamically based on 16 active hours per day, clamped to 2–8 minutes with ±20% jitter
