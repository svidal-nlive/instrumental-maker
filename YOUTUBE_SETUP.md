# YouTube Download Setup Guide

This document explains how YouTube downloads work in the Instrumental Maker and how bot detection is automatically handled.

## Overview

YouTube has anti-bot measures that can block downloads. The Instrumental Maker uses **two complementary approaches** to bypass these restrictions:

1. **PO Token Provider (Recommended - Automatic)** - A "set and forget" solution that runs as a Docker service
2. **Manual Cookies (Fallback)** - For cases where the PO Token provider is insufficient

## PO Token Provider (Automatic)

### What is it?
The PO Token Provider (`bgutil-ytdlp-pot-provider`) is a Docker service that automatically generates Proof-of-Origin (PO) tokens. These tokens prove to YouTube that requests are coming from legitimate clients.

### How it works
1. The `bgutil-provider` container runs an HTTP server on port 4416
2. When yt-dlp needs to download a video, it requests a PO token from this server
3. The token is included in requests to YouTube, bypassing bot detection
4. Tokens are automatically regenerated as needed

### Features
- ✅ **No setup required** - Just `docker compose up` and it works
- ✅ **No Google account needed** - Works without any login
- ✅ **Self-refreshing** - Tokens are generated on-demand
- ✅ **Fully automatic** - No manual intervention ever needed

### Checking Status
The WebUI shows the PO Token provider status in the "YouTube Download" section. A green indicator means it's running and ready.

## Manual Cookies (Fallback)

If the PO Token provider isn't working for some reason, you can use browser cookies as a fallback.

### How to get cookies
1. Open a **private/incognito** browser window
2. Go to YouTube and sign in with a throwaway account
3. Navigate to `https://www.youtube.com/robots.txt`
4. Export cookies using a browser extension:
   - Chrome: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
5. Upload the cookies file in the WebUI

### Important Notes
- ⚠️ **Close the incognito window immediately** after exporting - this prevents cookie rotation
- ⚠️ **Don't use cookies from your main browser** - YouTube can ban accounts
- ⚠️ **Cookies may expire** - You may need to regenerate them occasionally

## Architecture

```
                                    ┌─────────────────────┐
                                    │   bgutil-provider   │
                                    │   (PO Token Gen)    │
                                    │   Port: 4416        │
                                    └──────────▲──────────┘
                                               │
┌─────────────┐      ┌─────────────┐          │
│   Browser   │──────│   WebUI     │──────────┘
│             │      │  Port: 5000 │
└─────────────┘      └──────┬──────┘
                            │
                            ▼
                    ┌─────────────────────┐
                    │   yt-dlp            │
                    │   (with bgutil      │
                    │    plugin)          │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   YouTube           │
                    └─────────────────────┘
```

## Troubleshooting

### "Sign in to confirm you're not a bot" error
1. Check if the PO Token provider is running (green status in WebUI)
2. If provider is down, try restarting: `docker compose restart bgutil-provider`
3. As a fallback, upload cookies from an incognito browser session

### Downloads stalling
1. Make sure you're using single video URLs, not playlists
2. The system automatically strips playlist parameters from URLs
3. Check if the video is geo-restricted or members-only

### Provider not starting
1. Check Docker logs: `docker compose logs bgutil-provider`
2. Ensure port 4416 isn't in use by another service
3. Try pulling the latest image: `docker pull brainicism/bgutil-ytdlp-pot-provider`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YTDLP_POT_PROVIDER_URL` | `http://instrumental-bgutil:4416` | URL of the PO Token provider |
| `YTDLP_COOKIES_FILE` | `/data/config/cookies.txt` | Path to cookies file (fallback) |

## References

- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
- [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- [yt-dlp Extractors Wiki](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#youtube)
