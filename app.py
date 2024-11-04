from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import logging
import time
import urllib.parse
from typing import Optional
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Create necessary directories
STATIC_DIR = "static"
TEMPLATES_DIR = "templates"
DOWNLOAD_DIR = "downloads"
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str
    quality: Optional[str] = "highest"
    file_type: Optional[str] = "mp4"

def sanitize_url(url: str) -> str:
    """Sanitize and validate the YouTube URL"""
    try:
        parsed = urllib.parse.urlparse(url)
        return url if parsed.scheme and parsed.netloc else None
    except Exception as e:
        logger.error(f"Error sanitizing URL: {str(e)}")
        return None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/download")
async def download_video(video_request: VideoRequest, background_tasks: BackgroundTasks):
    try:
        logger.info(f"Received download request for URL: {video_request.url}")
        
        # Generate unique download ID
        download_id = str(uuid.uuid4())
        
        # Validate YouTube URL
        sanitized_url = sanitize_url(video_request.url)
        if not sanitized_url:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        try:
            # Set yt-dlp options with cookies file
            ydl_opts = {
                'format': 'bestaudio' if video_request.file_type == 'mp3' else 'best',
                'noplaylist': True,
                'outtmpl': os.path.join(DOWNLOAD_DIR, f"{download_id}.%(ext)s"),
                'cookiefile': 'cookies.txt'  # Add path to cookies file
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(sanitized_url, download=False)
                video_title = info_dict.get('title', 'video')
                logger.info(f"Successfully initialized video: {video_title}")

                # Start the download in the background
                background_tasks.add_task(download_with_ytdlp, ydl_opts, sanitized_url)
            
            return {
                "download_id": download_id,
                "message": "Download started",
                "title": video_title,
                "author": info_dict.get('uploader', 'unknown'),
                "length": info_dict.get('duration', 0)
            }
        
        except Exception as e:
            logger.error(f"Error initializing video download: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def download_with_ytdlp(ydl_opts, url):
    """Download video using yt-dlp with specified options."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise

@app.get("/api/status/{download_id}")
async def check_status(download_id: str):
    try:
        mp4_path = os.path.join(DOWNLOAD_DIR, f"{download_id}.mp4")
        mp3_path = os.path.join(DOWNLOAD_DIR, f"{download_id}.mp3")
        
        if os.path.exists(mp4_path) or os.path.exists(mp3_path):
            return {"status": "completed"}
        else:
            return {"status": "processing"}
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return {"status": "error", "detail": str(e)}

@app.get("/api/download/{download_id}")
async def get_file(download_id: str):
    mp4_path = os.path.join(DOWNLOAD_DIR, f"{download_id}.mp4")
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{download_id}.mp3")
    
    if os.path.exists(mp4_path):
        return FileResponse(mp4_path, filename=f"video_{download_id}.mp4")
    elif os.path.exists(mp3_path):
        return FileResponse(mp3_path, filename=f"audio_{download_id}.mp3")
    else:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
