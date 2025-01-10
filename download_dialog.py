from PyQt5.QtWidgets import QDialog, QListView, QTextEdit, QPushButton
from PyQt5.QtCore import Qt, QStringListModel, QSettings
from PyQt5.QtGui import QColor, QStandardItemModel, QStandardItem
from PyQt5 import uic
from channel_downloader import ChannelDownloader
from threading import Thread


class DownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi('download_dialog.ui', self)

        # Get widgets
        self.video_list = self.findChild(QListView, 'listView')
        self.output_text = self.findChild(QTextEdit, 'textEdit')
        self.start_button = self.findChild(QPushButton, 'pushButtonStart')
        self.stop_button = self.findChild(QPushButton, 'pushButtonStop')
        self.close_button = self.findChild(QPushButton, 'pushButtonClose')
        self.create_video_list_button = self.findChild(QPushButton, 'pushButtonVideoList')
        self.refresh_video_list_button = self.findChild(QPushButton, 'pushButtonRefreshVideoList')

        # Setup model
        self.list_model = QStandardItemModel()
        self.video_list.setModel(self.list_model)

        # Connect signals
        self.start_button.clicked.connect(self.start_download)
        self.stop_button.clicked.connect(self.stop_download)
        self.close_button.clicked.connect(self.close)
        self.create_video_list_button.clicked.connect(lambda: self.refresh_video_list(False))
        self.refresh_video_list_button.clicked.connect(lambda: self.refresh_video_list(True))

        # Initialize variables
        self.downloader = None
        self.download_thread = None
        self.video_list_thread = None

        # Initial button states
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        # Add selection change handler
        self.video_list.selectionModel().selectionChanged.connect(self.on_video_selected)
        self.metadata_text = self.findChild(QTextEdit, 'textEditMetadata')

    def setup(self, api_key: str, channel: str, output_dir: str, max_threads: int):
        self.api_key = api_key
        self.channel = channel
        self.output_dir = output_dir
        self.max_threads = max_threads

        # Create downloader with settings
        self.downloader = ChannelDownloader(
            api_key=api_key,
            output_dir=output_dir,
            max_threads=max_threads,
            progress_callback=self.log_progress,
            settings=QSettings('YVD', 'YoutubeVideoDownloader')
        )

        # Don't automatically refresh - wait for user action
        self.create_video_list_button.setEnabled(True)
        self.start_button.setEnabled(False)

    def log_progress(self, message: str):
        self.output_text.append(message)

    def on_video_selected(self, selected, deselected):
        """Handle video selection change"""
        indexes = selected.indexes()
        if not indexes:
            return

        url = self.list_model.data(indexes[0], Qt.DisplayRole)
        try:
            metadata = self.downloader.get_video_metadata(url)
            self.metadata_text.setText(metadata.model_dump_json(indent=4))
        except Exception as e:
            self.log_progress(f"Error loading metadata: {str(e)}")
            self.metadata_text.setText("Error loading metadata")

    def refresh_video_list(self, force_refresh: bool = True):
        """Refresh video list in background thread"""
        if self.video_list_thread and self.video_list_thread.is_alive():
            return

        self.create_video_list_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.list_model.clear()
        self.metadata_text.clear()
        self.log_progress(f"Fetching video list...")

        def update_list():
            try:
                channel_id = self.downloader.get_channel_id(self.channel)
                urls = self.downloader.get_video_urls(channel_id, self.channel, force_refresh)

                self.list_model.clear()
                for url in urls:
                    item = QStandardItem(url)
                    if self.downloader.is_video_downloaded(url):
                        item.setBackground(QColor(200, 255, 200))  # Light green
                    else:
                        item.setBackground(QColor(255, 200, 200))  # Light red
                    self.list_model.appendRow(item)

                self.log_progress(f"Found {len(urls)} videos")
                self.create_video_list_button.setEnabled(True)
                self.start_button.setEnabled(True)

            except Exception as e:
                self.log_progress(f"Error getting video list: {str(e)}")
                self.create_video_list_button.setEnabled(True)

        self.video_list_thread = Thread(target=update_list, daemon=True)
        self.video_list_thread.start()

    def start_download(self):
        if self.download_thread and self.download_thread.is_alive():
            return

        # First ensure we have video list
        if self.list_model.rowCount() == 0:
            self.refresh_video_list(force_refresh=False)
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.create_video_list_button.setEnabled(False)

        self.download_thread = Thread(
            target=self.download_videos,
            daemon=True
        )
        self.download_thread.start()

    def download_videos(self):
        try:
            channel_id = self.downloader.get_channel_id(self.channel)
            video_urls = self.downloader.get_video_urls(channel_id, self.channel, force_refresh=False)

            for url in video_urls:
                if self.downloader._stop_requested:
                    break

                success = self.downloader.download_video(url)

                # Update list view item color
                for row in range(self.list_model.rowCount()):
                    item = self.list_model.item(row)
                    if item.text() == url:
                        item.setBackground(QColor(200, 255, 200) if success else QColor(255, 200, 200))
                        break

        except Exception as e:
            self.log_progress(f"Error during download: {str(e)}")
        finally:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.create_video_list_button.setEnabled(True)

    def stop_download(self):
        if self.downloader:
            self.downloader.stop()
            self.stop_button.setEnabled(False)
            self.log_progress("Download stopped by user")
