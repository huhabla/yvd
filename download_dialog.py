import os
from PyQt5.QtWidgets import QDialog, QListView, QTextEdit, QPushButton
from PyQt5.QtCore import Qt, QStringListModel, QSettings, QUrl
from PyQt5.QtGui import QColor, QStandardItemModel, QStandardItem
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import uic
from channel_downloader import ChannelDownloader
from threading import Thread
from datetime import datetime


class VideoListItem(QStandardItem):
    def __init__(self, url: str, metadata=None):
        # Create display text
        if metadata:
            # Format date and truncate title
            date_str = metadata.date.strftime('%Y-%m-%d') if metadata.date else "No date"

            # Format video length
            length_mins = metadata.length // 60
            length_secs = metadata.length % 60
            length_str = f"{length_mins}:{str(length_secs).zfill(2)} min"

            title = metadata.title[:50] + "..." if len(metadata.title) > 50 else metadata.title
            display_text = f"{date_str} - {length_str} - {title}"
        else:
            display_text = url

        super().__init__(display_text)

        # Store URL as item data
        self.setData(url, Qt.UserRole)
        self.setEditable(False)


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
        self.single_download_button = self.findChild(QPushButton, 'pushButtonSingleDownload')
        self.web_view = self.findChild(QWebEngineView, 'webEngineView')
        self.metadata_text = self.findChild(QTextEdit, 'textEditMetadata')

        # Setup model
        self.list_model = QStandardItemModel()
        self.video_list.setModel(self.list_model)

        # Connect signals
        self.start_button.clicked.connect(self.start_download)
        self.stop_button.clicked.connect(self.stop_download)
        self.close_button.clicked.connect(self.close)
        self.create_video_list_button.clicked.connect(lambda: self.refresh_video_list(False))
        self.refresh_video_list_button.clicked.connect(lambda: self.refresh_video_list(True))
        self.single_download_button.clicked.connect(self.download_selected_video)
        self.video_list.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # Initialize variables
        self.downloader = None
        self.download_thread = None
        self.video_list_thread = None

        # Initial button states
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.single_download_button.setEnabled(False)

    def setup(self, channel: str, output_dir: str, max_threads: int):
        self.channel = channel
        self.output_dir = output_dir
        self.max_threads = max_threads

        # Create downloader with settings
        self.downloader = ChannelDownloader(
            output_dir=output_dir,
            max_threads=max_threads,
            progress_callback=self.log_progress,
            settings=QSettings('YVD', 'YoutubeVideoDownloader')
        )

        # Don't automatically refresh - wait for user action
        self.create_video_list_button.setEnabled(True)
        self.start_button.setEnabled(False)
        self.refresh_video_list(False)

    def on_selection_changed(self, selected, deselected):
        """Enable/disable single download button based on selection"""
        self.single_download_button.setEnabled(len(selected.indexes()) > 0)

        # Update web view and metadata
        indexes = selected.indexes()
        if indexes:
            url = self.list_model.data(indexes[0], Qt.UserRole)

            # Update web view
            if self.web_view:
                self.web_view.setUrl(QUrl(url))

            # Update metadata
            try:
                metadata = self.downloader.get_video_metadata(url)

                # Load HTML template
                template_path = os.path.join(os.path.dirname(__file__), 'metadata_template.html')
                with open(template_path, 'r', encoding='utf-8') as f:
                    html_template = f.read()

                # Format video length
                length_mins = metadata.length // 60
                length_secs = metadata.length % 60
                length_str = f"{length_mins}:{str(length_secs).zfill(2)} minutes"

                # Format keywords
                keywords_html = ''.join(
                    [f'<span class="keywords">{k}</span>' for k in metadata.keywords]) if metadata.keywords else 'None'

                # Format date
                date_str = metadata.date.strftime('%Y-%m-%d %H:%M:%S') if metadata.date else 'Unknown'

                # Replace placeholders in template
                html_content = html_template.format(
                    title=metadata.title,
                    author=metadata.author,
                    date=date_str,
                    length=length_str,
                    channel_url=metadata.channel_url,
                    url=metadata.url,
                    description=metadata.description or 'No description available',
                    keywords=keywords_html
                )

                # Set HTML content
                self.metadata_text.setHtml(html_content)

            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                self.log_progress(f"Error loading metadata: {str(e)}")
                error_html = f"""
                        <html>
                            <head>
                                <style>
                                    body {{
                                        color: red;
                                        font-family: Arial, sans-serif;
                                        margin: 20px;
                                    }}
                                    .error-title {{
                                        font-size: 18px;
                                        font-weight: bold;
                                        margin-bottom: 10px;
                                    }}
                                    .error-message {{
                                        margin-bottom: 15px;
                                    }}
                                    .traceback {{
                                        font-family: monospace;
                                        white-space: pre-wrap;
                                        background-color: #ffeeee;
                                        padding: 10px;
                                        border: 1px solid #ffcccc;
                                        border-radius: 4px;
                                    }}
                                </style>
                            </head>
                            <body>
                                <div class="error-title">Error loading metadata</div>
                                <div class="error-message">{str(e)}</div>
                                <div class="traceback">{error_traceback}</div>
                            </body>
                        </html>
                    """
                self.metadata_text.setHtml(error_html)

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
                urls = self.downloader.get_video_urls(self.channel, force_refresh)

                self.list_model.clear()
                for url in urls:
                    # For regular list loading, just check if metadata exists
                    metadata_exists = os.path.exists(
                        self.downloader.get_metadata_path(self.downloader.get_video_id(url)))

                    if force_refresh and not metadata_exists:
                        # Only load metadata if refresh button was clicked and metadata doesn't exist
                        try:
                            metadata = self.downloader.get_video_metadata(url, force_refresh=False)
                            item = VideoListItem(url, metadata)
                        except Exception as e:
                            self.log_progress(f"Error loading metadata for {url}: {str(e)}")
                            item = VideoListItem(url)
                    else:
                        # For initial list loading or if metadata exists
                        if metadata_exists:
                            try:
                                metadata = self.downloader.get_video_metadata(url, force_refresh=False)
                                item = VideoListItem(url, metadata)
                            except:
                                item = VideoListItem(url)
                        else:
                            item = VideoListItem(url)

                    if self.downloader.is_video_downloaded(url):
                        item.setBackground(QColor(200, 255, 200))  # Light green
                    else:
                        item.setBackground(QColor(255, 200, 200))  # Light red

                    self.list_model.appendRow(item)

                self.log_progress(f"Found {len(urls)} videos")
                if force_refresh:
                    self.log_progress("Metadata refresh completed")
                self.create_video_list_button.setEnabled(True)
                self.start_button.setEnabled(True)

            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                self.log_progress(f"Error getting video list:  {str(e)} {error_traceback}")
                self.create_video_list_button.setEnabled(True)

        self.video_list_thread = Thread(target=update_list, daemon=True)
        self.video_list_thread.start()

    def download_selected_video(self):
        """Download currently selected video"""
        indexes = self.video_list.selectedIndexes()
        if not indexes:
            return

        # Get URL from item data
        url = self.list_model.data(indexes[0], Qt.UserRole)

        # Disable buttons during download
        self.single_download_button.setEnabled(False)
        self.start_button.setEnabled(False)

        def download_single():
            try:
                success = self.downloader.download_video(url)

                # Update list view item color
                for row in range(self.list_model.rowCount()):
                    item = self.list_model.item(row)
                    if item.data(Qt.UserRole) == url:
                        item.setBackground(QColor(200, 255, 200) if success else QColor(255, 200, 200))
                        break

                self.log_progress(f"Single video download {'completed' if success else 'failed'}: {url}")
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                self.log_progress(f"Error downloading video: {str(e)}  {error_traceback}")
            finally:
                # Re-enable buttons
                self.single_download_button.setEnabled(True)
                self.start_button.setEnabled(True)

        # Start download in background thread
        Thread(target=download_single, daemon=True).start()

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
            video_urls = self.downloader.get_video_urls(self.channel, force_refresh=False)

            for url in video_urls:
                if self.downloader._stop_requested:
                    break

                success = self.downloader.download_video(url)

                # Update list view item color
                for row in range(self.list_model.rowCount()):
                    item = self.list_model.item(row)
                    if item.data(Qt.UserRole) == url:
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

    def log_progress(self, message: str):
        self.output_text.append(message)
