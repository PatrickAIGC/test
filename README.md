# Patrick Reddit Bot (Debug Version)

This version is for Render deployment testing. It will:
- Log environment variables load status
- Print alive message every minute
- Not post anything to Reddit

## How to Deploy
1. Upload to GitHub
2. Connect repo to [Render.com](https://render.com)
3. Create a Background Worker:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
4. Add environment variables from `.env.example`

You should see logs within 1 minute after deployment.
