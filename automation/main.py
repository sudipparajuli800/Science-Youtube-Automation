import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

# Patch PIL.Image.ANTIALIAS for compatibility between modern Pillow (10+) and MoviePy 1.x
try:
    import PIL.Image
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
except ImportError:
    pass

# Add the current directory to sys.path to allow absolute imports within the automation package
sys.path.append(os.getcwd())

from automation.config_loader import ConfigLoader
from automation.media.visual_quality import VisualQualityHold, report_hold
from automation.pipelines.science_pipeline import SciencePipeline
from automation.youtube.auth import YouTubeAuth
from automation.youtube.comment_handler import CommentHandler

load_dotenv()

async def list_channels():
    config_dir = "automation/config"
    if not os.path.exists(config_dir):
        print("No configs found.")
        return
    for f in os.listdir(config_dir):
        if f.endswith(".yaml"):
            print(f" - {f}")

async def main():
    parser = argparse.ArgumentParser(description="Multi-Channel Autonomous Media Platform")
    parser.add_argument("--mode", default="breaking", choices=["breaking", "daily", "shorts", "storytelling", "comments", "social_post"], help="Execution mode")
    parser.add_argument("--test", action="store_true", help="Run in test mode (skip upload)")
    parser.add_argument("--list", action="store_true", help="List available channels")
    
    args = parser.parse_args()

    if args.list:
        await list_channels()
        return

    # Force load Science Config
    config = ConfigLoader.load_config("automation/config/science.yaml")

    if args.mode == "comments":
        print("--- Starting AI Comment Auto-Reply ---")
        
        # 1. YouTube comment replier
        try:
            youtube_service = YouTubeAuth.get_service(os.getenv("YOUTUBE_TOKEN_BASE64"))
            handler = CommentHandler(youtube_service, os.getenv("GEMINI_API_KEY"))
            channel_id = config.get("channel_id")
            handler.handle_comments(max_videos=25, channel_id=channel_id)
        except Exception as ye:
            print(f"YouTube comments handling failed: {ye}")
            
        # 2. Meta (Facebook/Instagram) comment replier
        try:
            from automation.meta.comment_handler import MetaCommentHandler
            meta_handler = MetaCommentHandler()
            meta_handler.handle_comments()
        except Exception as me:
            print(f"Meta comments handling failed: {me}")
            
        print("--- AI Comment Auto-Reply Completed ---")
        return

    # Run Pipeline directly
    pipeline = SciencePipeline(config)
    try:
        await pipeline.run(mode=args.mode, is_test=args.test)
    except VisualQualityHold as hold:
        report_hold(str(hold))

if __name__ == "__main__":
    asyncio.run(main())
