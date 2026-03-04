# Sound-Based Scraping Redesign

> **Date:** 2026-03-04
> **Status:** Design approved, pending implementation
> **Problem:** Profile-based Apify scraping burned $40 in credits in 2 days and hit the monthly usage limit. 258 creator profiles × 100 videos = 25,800 videos per refresh at $3.70/1,000 = ~$95/refresh.

## Solution

Replace profile-based scraping with sound-based scraping for campaigns, and revert to free yt-dlp for internal network.

### External Campaigns: apidojo Sound Scraper (Daily)

**Actor:** `apidojo/tiktok-music-scraper`
**Schedule:** Daily 6 AM EST
**Cost:** ~$4.65/day → ~$140/mo

**How it works:**
1. For each active campaign, build a TikTok sound URL from the `sound_id` (and any `additional_sounds`)
2. Call apidojo actor with those sound URLs → returns all videos that used each sound
3. Filter results: is the video's author in our creator list for this campaign?
4. If yes → matched video, save to DB, update stats

**Inverted lookup:** Instead of scraping 258 profiles and checking if any video matches the sound, we scrape ~31 sounds and check if any video was posted by our creators. Same result, 20x cheaper.

**Input format:**
```json
{
  "startUrls": ["https://www.tiktok.com/music/sound-7607726203173095425"],
  "maxItems": 500
}
```

**Pricing:** ~$0.30/1,000 videos. First ~11 posts per query are free.

**What it won't catch:** Creators who post using "original sound - Artist" instead of the official campaign sound. This is rare (only happened once with Chezile). When it does happen, Jake can trigger a manual profile-based refresh from the campaign page UI.

### Internal Network: yt-dlp (Daily)

**Tool:** yt-dlp (free, runs on Railway container)
**Schedule:** Daily 6 AM EST (staggered 2 min after campaign refresh)
**Cost:** $0

**How it works:**
1. Get all internal creator usernames
2. For each creator, use yt-dlp to pull recent video metadata (song, artist, views)
3. Group by song, update caches, save results

yt-dlp can't reliably extract `musicId`, but internals don't need it — we just need song name + artist for trending song discovery.

### Manual Profile Refresh (On-Demand)

The existing profile-based Apify scrape (`clockworks/tiktok-scraper`) stays available via the campaign detail page's refresh button. This is the fallback for edge cases (original sounds, missing matches). Not scheduled — triggered manually by Jake when needed.

## Scheduler Changes

| Job | Schedule | Actor/Tool | What |
|---|---|---|---|
| `campaign_sound_refresh` | Daily 6 AM EST | apidojo/tiktok-music-scraper | Sound-based campaign matching |
| `internal_scrape` | Daily 6:02 AM EST | yt-dlp | Internal creator song discovery |

The existing `campaign_refresh` cron job gets replaced by `campaign_sound_refresh`. The interactive refresh button on campaign pages continues to use the profile-based Apify scraper for on-demand use.

## Files to Change

| File | Change |
|---|---|
| `campaign_manager/services/apify_scraper.py` | Add `scrape_by_sound()` using apidojo actor |
| `campaign_manager/services/scheduler.py` | Replace `run_campaign_refresh` with sound-based logic, revert `run_internal_scrape` to yt-dlp |
| `campaign_manager/config.py` | Add `APIDOJO_ACTOR_ID` config |
| `requirements.txt` | Ensure yt-dlp is still listed (it is) |

## Cost Summary

| Component | Before | After |
|---|---|---|
| Campaign refresh (daily) | $95.46/day ($2,864/mo) | $4.65/day ($140/mo) |
| Internal scrape (daily) | $5.55/day ($167/mo) | $0 (yt-dlp) |
| **Total** | **~$3,031/mo** | **~$140/mo** |

95% cost reduction.
