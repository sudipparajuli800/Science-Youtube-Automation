# International News Automation System

A fully automated international news publishing system that detects breaking news for YouTube Shorts and produces daily summaries for long-form videos.

## Features
- **Breaking News Detection**: Scans RSS feeds, Telegram, and DDG for urgent updates.
- **AI Scripting**: Uses Google Gemini to rewrite news into catchy video scripts.
- **Natural Narration**: High-quality English voiceovers via `edge-tts`.
- **Vertical & Horizontal Video**: Programmatically generates video with animated subtitles.
- **Auto-Upload**: Publishes directly to YouTube with optimized metadata.
- **Hands-Free**: Powered by GitHub Actions for periodic execution.

## Project Structure
```
international_news_automation/
├── fetchers/            # RSS, Telegram, and DDG fetchers
├── processors/          # Classification and AI scripting
├── media/               # TTS and video generation logic
├── uploader/            # YouTube API integration
├── storage/             # Trackers and temporary media
├── main_breaking.py     # Entry point for Shorts
├── main_daily.py        # Entry point for Daily Summaries
└── .github/workflows/   # Scheduling logic
```

## Setup Instructions

### 1. Prerequisites
- **Python 3.9+**
- **FFmpeg**: [Download here](https://ffmpeg.org/download.html) and add to PATH.
- **Pillow** renders captions, thumbnails and explanation cards. ImageMagick and policy-file edits are not required.

### 2. API Credentials
- **Gemini AI**: Add `GEMINI_API_KEY` to your `.env` file. The system is configured to use `gemini-2.0-flash`.
- **YouTube API**: 
  - Place `client_secrets.json` in the project root.
  - Run the script once locally. It will open a browser for authentication and create `token.pickle`.
- **Telegram (Optional)**: Get `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 4. Running Locally
```bash
pip install -r requirements.txt
python international_news_automation/main_breaking.py
```

## GitHub Actions Deployment
1. Go to your GitHub Repository Settings -> Secrets and variables -> Actions.
2. Add the following secrets:
   - `GEMINI_API_KEY`
   - `TELEGRAM_API_ID` (if used)
   - `TELEGRAM_API_HASH` (if used)
3. Ensure the `token.pickle` is committed to the repository (or handle authentication via service accounts if preferred).

## Monetization Compliance
- Content is rewritten from scratch (no verbatim copying).
- Original narration (no source audio used).
- Educational/News context (Transformative work).
