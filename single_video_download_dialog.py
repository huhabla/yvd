# Add these imports at the top of main.py
from PyQt5.QtWidgets import QFileDialog, QVBoxLayout, QTextEdit, QProgressDialog, QDialog
from PyQt5.QtCore import QUrl, Qt, QSettings
from channel_downloader import ChannelDownloader
import os


# Add this new dialog class in main.py
class SingleVideoDownloadDialog(QDialog):
    def __init__(self, url: str, output_dir: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Downloading Video")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        layout = QVBoxLayout()

        # Progress text display
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        layout.addWidget(self.progress_text)

        self.setLayout(layout)

    def log_progress(self, message: str):
        self.progress_text.append(message)

    def download_video(self, save_path: str):
        try:
            # Create downloader instance
            downloader = ChannelDownloader(
                output_dir=os.path.dirname(save_path),
                progress_callback=self.log_progress,
                settings=QSettings('YVD', 'YoutubeVideoDownloader')
            )

            # Get video metadata first
            self.log_progress("Getting video metadata...")
            metadata = downloader.get_video_metadata(self.url)

            # Download the video
            self.log_progress(f"Downloading: {metadata.title}")

            # Download video and rename to target path
            success = downloader.download_video(self.url, save_path)

            if success:
                self.log_progress("Download completed successfully!")
            else:
                self.log_progress("Download failed!")

        except Exception as e:
            import traceback
            self.log_progress(f"Error: {str(e)}\n{traceback.format_exc()}")
