from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable
from datetime import datetime
import os
import json

from PyQt5.QtCore import QSettings
from googleapiclient.discovery import build
from pytubefix import YouTube
import requests
from pydantic import BaseModel
import logging
from typing import Optional
from pytubefix import Stream
from PyQt5.QtWidgets import QComboBox

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VideoMetadataModel(BaseModel):
    file_name: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    length: int = 0
    date: datetime = ""
    keywords: List[str] = []
    channel_url: str = ""
    metadata: List[dict] = None


class ChannelDownloader:
    def __init__(self, api_key: str, output_dir: str, max_threads: int = 4,
                 progress_callback: Callable[[str], None] = print,
                 settings: QSettings = None):
        self.api_key = api_key
        self.output_dir = output_dir
        self.max_threads = max_threads
        self.progress_callback = progress_callback
        self._stop_requested = False
        self.current_channel_dir = None
        self.settings = settings or QSettings('YVD', 'YoutubeVideoDownloader')

    def get_channel_dir(self, channel_name: str) -> str:
        """Create and return channel-specific directory"""
        channel_dir = os.path.join(self.output_dir, channel_name)
        if not os.path.exists(channel_dir):
            os.makedirs(channel_dir)
        return channel_dir

    def get_video_list_file(self, channel_name: str) -> str:
        """Get path to video list JSON file"""
        channel_dir = self.get_channel_dir(channel_name)
        return os.path.join(channel_dir, 'video_list.json')

    def get_video_id(self, url: str) -> str:
        """Extract video ID from URL"""
        if "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        return url.split("/")[-1]

    def get_video_path(self, video_id: str) -> str:
        """Get video file path from video ID"""
        return os.path.join(self.current_channel_dir or self.output_dir, f"{video_id}.mp4")

    def get_metadata_path(self, video_id: str) -> str:
        """Get metadata file path from video ID"""
        return os.path.join(self.current_channel_dir or self.output_dir, f"{video_id}.json")

    def get_channel_id(self, channel_name: str) -> str:
        logger.info(f"Getting channel ID for: {channel_name}")
        if channel_name.startswith("UC"):
            return channel_name

        url = f"https://www.googleapis.com/youtube/v3/channels?key={self.api_key}&forHandle=%40{channel_name}&part=id"
        response = requests.get(url)
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            channel_id = data["items"][0]["id"]
            logger.info(f"Found channel ID: {channel_id}")
            return channel_id
        raise ValueError(f"Channel not found: {data}")

    def get_video_urls(self, channel_name: str, force_refresh: bool = False) -> List[str]:
        """Get video URLs from cache or YouTube API"""

        self.current_channel_dir = self.get_channel_dir(channel_name)
        video_list_file = self.get_video_list_file(channel_name)

        if not force_refresh and os.path.exists(video_list_file):
            logger.info("Loading cached video list...")
            self.progress_callback("Loading cached video list...")
            with open(video_list_file, 'r') as f:
                data = json.load(f)
                return data['urls']

        channel_id = self.get_channel_id(channel_name)
        logger.info(f"{channel_name} -> {channel_id}")
        logger.info("Fetching video list from YouTube API...")
        self.progress_callback("Fetching video list from YouTube API...")
        youtube = build("youtube", "v3", developerKey=self.api_key)
        video_urls = []
        next_page_token = None
        page_count = 0

        while not self._stop_requested:
            page_count += 1
            logger.info(f"Fetching page {page_count}...")
            self.progress_callback(f"Fetching page {page_count}...")

            search_response = youtube.search().list(
                channelId=channel_id,
                part="snippet",
                maxResults=50,
                order="date",
                pageToken=next_page_token
            ).execute()

            for item in search_response.get("items", []):
                if item["id"]["kind"] == "youtube#video":
                    video_id = item["id"]["videoId"]
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    video_urls.append(url)
                    logger.info(f"Found video: {url}")
                    # self.progress_callback(f"Found video: {url}")

            next_page_token = search_response.get("nextPageToken")
            if not next_page_token:
                break

        # Save to file
        logger.info(f"Saving video list ({len(video_urls)} videos)...")
        self.progress_callback(f"Saving video list ({len(video_urls)} videos)...")
        with open(video_list_file, 'w') as f:
            json.dump({
                'channel_id': channel_id,
                'updated_at': datetime.now().isoformat(),
                'urls': video_urls
            }, f, indent=2)

        return video_urls

    def is_video_downloaded(self, url: str) -> bool:
        """Check if video exists using video ID - only check for final filename"""
        video_id = self.get_video_id(url)
        final_path = self.get_video_path(video_id)
        return os.path.exists(final_path) and os.path.getsize(final_path) > 0

    def save_video_metadata(self, yt: YouTube, video_id: str):
        """Save video metadata to JSON file"""
        metadata = VideoMetadataModel(
            file_name=video_id,
            url=yt.watch_url,
            title=yt.title,
            description=yt.description,
            author=yt.author,
            length=yt.length,
            date=yt.publish_date,
            keywords=yt.keywords,
            channel_url=yt.channel_url,
            metadata=yt.metadata
        )

        meta_path = self.get_metadata_path(video_id)
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=4))

    def get_video_metadata(self, url: str, force_refresh: bool = False) -> VideoMetadataModel:
        """Get video metadata from cache or YouTube"""
        video_id = self.get_video_id(url)
        meta_path = self.get_metadata_path(video_id)

        if not force_refresh and os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return VideoMetadataModel.model_validate_json(f.read())

        # Download fresh metadata
        yt = YouTube(url)
        self.save_video_metadata(yt, video_id)
        return self.get_video_metadata(url)

    # Add these methods to the ChannelDownloader class in channel_downloader.py

    def get_temp_video_path(self, video_id: str) -> str:
        """Get temporary video file path during download"""
        return os.path.join(self.current_channel_dir or self.output_dir, f"{video_id}.downloading.mp4")

    def rename_video_files(self, video_id: str, new_path: str):
        """Rename video and metadata files to new location"""
        # Get current file paths
        current_video_path = self.get_video_path(video_id)
        current_meta_path = self.get_metadata_path(video_id)

        # Get new metadata path based on new video path
        new_meta_path = os.path.splitext(new_path)[0] + '.json'

        try:
            # Rename video file if it exists
            if os.path.exists(current_video_path):
                os.rename(current_video_path, new_path)

            # Rename metadata file if it exists
            if os.path.exists(current_meta_path):
                os.rename(current_meta_path, new_meta_path)

            return True
        except Exception as e:
            import traceback
            self.progress_callback(f"Error renaming files: {str(e)}\n{traceback.format_exc()}")
            return False

    def download_video(self, url: str, target_path: str = None) -> bool:
        """Download video with optional target path for renaming"""
        if self._stop_requested:
            return False

        try:
            video_id = self.get_video_id(url)
            output_dir = self.current_channel_dir or self.output_dir

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Change to output directory temporarily
            original_dir = os.getcwd()
            os.chdir(output_dir)

            temp_filename = f"{video_id}.downloading.mp4"
            final_filename = f"{video_id}.mp4"

            try:
                # Remove any incomplete downloads if they exist
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

                # Download video
                yt = YouTube(url)
                # Get stream based on resolution setting
                resolution = self.settings.value('preferred_resolution', '1080p')
                stream = self.get_stream_by_resolution(yt, resolution)
                self.progress_callback(f"DEBUG: Selected stream resolution: {stream.resolution if stream else 'None'}")
                self.progress_callback(f"DEBUG: Available streams: {[s.resolution for s in yt.streams.filter(progressive=True, file_extension='mp4')]}")

                if not stream:
                    self.progress_callback(
                        f"Requested resolution {resolution} not available, falling back to highest resolution")
                    stream = yt.streams.get_highest_resolution()

                # Save metadata first
                self.save_video_metadata(yt, video_id)

                self.progress_callback(f"Downloading: {yt.title} ({stream.resolution})")

                # Download using temporary filename
                stream.download(filename=temp_filename)

                # Verify file exists and has size > 0
                if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                    # Rename temporary file to final filename
                    os.replace(temp_filename, final_filename)
                    self.progress_callback(f"Completed: {yt.title}")

                    # If target path is specified, rename files
                    if target_path:
                        if self.rename_video_files(video_id, target_path):
                            self.progress_callback(f"Files renamed to: {target_path}")
                        else:
                            self.progress_callback("Failed to rename files")

                    return True
                else:
                    self.progress_callback(f"Download failed - file empty or missing: {yt.title}")
                    return False

            finally:
                # Clean up temporary file if it exists
                try:
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                except Exception as e:
                    import traceback
                    self.progress_callback(f"Error cleaning up temporary file: {str(e)}\n{traceback.format_exc()}")

                # Always restore the original directory
                os.chdir(original_dir)

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            self.progress_callback(f"Error downloading {url}: {str(e)}\n{error_traceback}")
            return False

    def get_stream_by_resolution(self, yt: YouTube, preferred_resolution: str) -> Optional[Stream]:
        """Get best stream matching preferred resolution"""
        # Get all progressive streams (with video and audio) sorted by resolution
        streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()

        if not streams:
            self.progress_callback("No suitable streams found")
            return None

        # Convert preferred resolution to integer for comparison
        target_res = int(preferred_resolution.replace('p', ''))

        # Log available resolutions for debugging
        available_resolutions = [s.resolution for s in streams]
        self.progress_callback(f"Available resolutions: {available_resolutions}")

        # First try exact match
        exact_match = streams.filter(resolution=preferred_resolution).first()
        if exact_match:
            self.progress_callback(f"Found exact resolution match: {exact_match.resolution}")
            return exact_match

        # If no exact match, get the highest resolution that's less than or equal to preferred
        for stream in streams:
            if not stream.resolution:
                continue

            current_res = int(stream.resolution.replace('p', ''))
            if current_res <= target_res:
                self.progress_callback(f"Selected closest resolution: {stream.resolution}")
                return stream

        # If no suitable resolution found, return highest available
        highest = streams.first()
        if highest:
            self.progress_callback(f"Falling back to highest available resolution: {highest.resolution}")
            return highest

        # Last resort - return any available stream
        self.progress_callback("No preferred resolution available, using first available stream")
        return streams.first()

    def stop(self):
        logger.info("Stopping download process...")
        self._stop_requested = True

    def download_channel(self, channel_name: str) -> List[str]:
        self._stop_requested = False
        logger.info(f"Starting download for channel: {channel_name}")

        self.current_channel_dir = self.get_channel_dir(channel_name)
        video_urls = self.get_video_urls(channel_name)

        if not os.path.exists(self.current_channel_dir):
            os.makedirs(self.current_channel_dir)

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            results = list(executor.map(self.download_video, video_urls))

        return video_urls


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    downloader = ChannelDownloader(
        api_key=args.api_key,
        output_dir=args.output_dir,
        max_threads=args.threads
    )
    downloader.download_channel(args.channel)


if __name__ == "__main__":
    main()
