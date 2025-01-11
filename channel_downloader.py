from concurrent.futures import ThreadPoolExecutor
from random import randrange
from typing import List, Callable, Optional, Any
from datetime import datetime
import os
import json
from PyQt5.QtCore import QSettings
from pytubefix import YouTube, Channel, Stream
from pydantic import BaseModel
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VideoMetadataModel(BaseModel):
    file_name: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    length: int = 0
    date: Optional[datetime] = None
    keywords: List[str] = []
    channel_url: str = ""
    metadata: Optional[Any] = None


class ChannelDownloader:
    def __init__(self, output_dir: str, max_threads: int = 4,
                 progress_callback: Callable[[str], None] = print,
                 settings: QSettings = None):
        self.output_dir = output_dir
        self.max_threads = max_threads
        self.progress_callback = progress_callback
        self._stop_requested = False
        self.current_channel_dir = None
        self.settings = settings or QSettings('YVD', 'YoutubeVideoDownloader')

    def get_channel_dir(self, channel_name: str) -> str:
        """Create and return channel-specific directory"""
        channel_dir = os.path.join(self.output_dir, channel_name.replace('@', ''))
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

    def get_video_urls(self, channel_name: str, force_refresh: bool = False) -> List[str]:
        """Get video URLs from cache or YouTube"""
        self.current_channel_dir = self.get_channel_dir(channel_name)
        video_list_file = self.get_video_list_file(channel_name)

        if not force_refresh and os.path.exists(video_list_file):
            self.progress_callback("Loading cached video list...")
            with open(video_list_file, 'r') as f:
                data = json.load(f)
                return data['urls']

        self.progress_callback("Fetching video list from channel...")

        # Convert @username to full URL if needed
        if channel_name.startswith('@'):
            channel_url = f"https://www.youtube.com/{channel_name}"
        else:
            channel_url = f"https://www.youtube.com/@{channel_name}"

        channel = Channel(channel_url)
        video_urls = []

        try:
            for idx, video in enumerate(channel.videos):
                if self._stop_requested:
                    break
                video_urls.append(video.watch_url)
                self.save_video_metadata(video, video.video_id)
                self.progress_callback(f"{idx} Found video: {video.title}")
                # Sleep a random number between 0 and 2 seconds to avoid detection as bot
                sleep_time = randrange(1,20)/20.0
                self.progress_callback(f"Sleep {sleep_time}")
                time.sleep(sleep_time)
        except Exception as e:
            import traceback
            self.progress_callback(f"Error receiving the video urls: {str(e)}\n{traceback.format_exc()}")

        # Save to file
        self.progress_callback(f"Saving video list ({len(video_urls)} videos)...")
        with open(video_list_file, 'w') as f:
            json.dump({
                'channel_name': channel.channel_name,
                'updated_at': datetime.now().isoformat(),
                'urls': video_urls
            }, f, indent=2)

        return video_urls

    def is_video_downloaded(self, url: str) -> bool:
        """Check if video exists and is complete"""
        video_id = self.get_video_id(url)
        final_path = self.get_video_path(video_id)
        return os.path.exists(final_path) and os.path.getsize(final_path) > 0

    def get_temp_video_path(self, video_id: str) -> str:
        """Get temporary video file path during download"""
        return os.path.join(self.current_channel_dir or self.output_dir, f"{video_id}.downloading.mp4")

    def save_video_metadata(self, yt: YouTube, video_id: str):
        """Save video metadata to JSON file"""
        try:
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
            )

            meta_path = self.get_metadata_path(video_id)
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(metadata.model_dump_json(indent=4))
            return meta_path
        except Exception as e:
            import traceback
            self.progress_callback(f"Unable to save video metadata for {video_id}: {str(e)}\n{traceback.format_exc()}")
            return None

    def get_video_metadata(self, url: str, force_refresh: bool = False) -> VideoMetadataModel:
        """Get video metadata from cache or YouTube"""
        video_id = self.get_video_id(url)
        meta_path = self.get_metadata_path(video_id)

        if not force_refresh and os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return VideoMetadataModel.model_validate_json(f.read())

        yt = YouTube(url)
        self.save_video_metadata(yt, video_id)
        return self.get_video_metadata(url)

    def get_stream_by_resolution(self, yt: YouTube, preferred_resolution: str) -> Optional[Stream]:
        """Get best stream matching preferred resolution"""
        streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()

        if not streams:
            self.progress_callback("No suitable streams found")
            return None

        target_res = int(preferred_resolution.replace('p', ''))

        # Try exact match first
        exact_match = streams.filter(resolution=preferred_resolution).first()
        if exact_match:
            return exact_match

        # Get closest lower resolution
        for stream in streams:
            if not stream.resolution:
                continue
            current_res = int(stream.resolution.replace('p', ''))
            if current_res <= target_res:
                return stream

        # Fall back to highest available
        return streams.first()

    def download_video(self, url: str, target_path: str = None) -> bool:
        """Download video with optional target path for renaming"""
        if self._stop_requested:
            return False

        try:
            video_id = self.get_video_id(url)
            temp_path = self.current_channel_dir or self.output_dir
            temp_file_name = f"{video_id}.downloading.mp4"
            temp_file_path = os.path.join(temp_path, temp_file_name)
            final_path = target_path or self.get_video_path(video_id)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(final_path), exist_ok=True)

            # Download video
            yt = YouTube(url)

            # Define progress callback
            def on_progress(stream, chunk, bytes_remaining):
                if self._stop_requested:
                    raise Exception("Download cancelled by user")

                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = (bytes_downloaded / total_size) * 100

                # Update progress every 1%
                if int(percentage) % 1 == 0:
                    self.progress_callback(
                        f"Downloading {yt.title}: {percentage:.1f}% "
                        f"({bytes_downloaded / (1024 * 1024):.1f}MB / {total_size / (1024 * 1024):.1f}MB)"
                    )

            # Register progress callback
            yt.register_on_progress_callback(on_progress)

            resolution = self.settings.value('preferred_resolution', '1080p')
            stream = self.get_stream_by_resolution(yt, resolution)

            if not stream:
                self.progress_callback(f"No suitable stream found for {url}")
                return False

            self.progress_callback(f"Starting download: {yt.title} ({stream.resolution})")

            # Download to temporary file
            stream.download(output_path=temp_path, filename=temp_file_name)

            # Move to final location if download successful
            if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                os.replace(temp_file_path, final_path)
                self.progress_callback(f"Completed: {yt.title}")
                # Save metadata
                meta_path = self.save_video_metadata(yt, video_id)
                if os.path.exists(meta_path):
                    os.replace(meta_path, final_path + ".json")
                return True
            else:
                self.progress_callback(f"Video was not downloaded: {yt.title}")
                return False

        except Exception as e:
            import traceback
            self.progress_callback(f"Error downloading {url}: {str(e)}\n{traceback.format_exc()}")
            return False
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass

    def stop(self):
        """Stop ongoing downloads"""
        self._stop_requested = True

    def download_channel(self, channel_name: str) -> List[str]:
        """Download all videos from a channel"""
        self._stop_requested = False
        self.current_channel_dir = self.get_channel_dir(channel_name)
        video_urls = self.get_video_urls(channel_name)

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            results = list(executor.map(self.download_video, video_urls))

        return video_urls
