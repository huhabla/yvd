import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QListView, QPushButton,
    QTextEdit, QLineEdit, QToolButton, QLabel,
    QMenuBar, QMenu, QAction, QDialog, QFileDialog
)
from PyQt5 import QtWidgets, uic
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QStringListModel, QUrl, QSettings, Qt

from channel_downloader import ChannelDownloader
from settings_dialog import SettingsDialog
from download_dialog import DownloadDialog
from single_video_download_dialog import SingleVideoDownloadDialog


class ChannelsModel(QStringListModel):
    def __init__(self, filename='channels.txt'):
        super().__init__()
        self.load_channels(filename)

    def load_channels(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                channels = [line.strip() for line in f.readlines() if line.strip()]
            self.setStringList(channels)
        except FileNotFoundError:
            print(f"Warning: {filename} not found. Creating empty channel list.")
            self.setStringList([])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('YVD', 'YoutubeVideoDownloader')

        # Load the UI file
        uic.loadUi('main_window.ui', self)

        # Create menu bar
        self.create_menu_bar()

        # Store references to all important widgets
        self.channels_list = self.findChild(QListView, 'listView')
        self.reload_button = self.findChild(QPushButton, 'pushButtonReload')
        self.api_key_input = self.findChild(QLineEdit, 'lineEditApiKey')
        self.output_dir_input = self.findChild(QLineEdit, 'lineEditOutputDir')
        self.browse_button = self.findChild(QToolButton, 'toolButton')
        self.web_view = self.findChild(QWebEngineView, 'webEngineView')
        self.url_label = self.findChild(QLabel, 'labelUrl')
        self.download_button = self.findChild(QPushButton, 'pushButtonDownload')
        self.forward_button = self.findChild(QPushButton, 'pushButtonForward')
        self.back_button = self.findChild(QPushButton, 'pushButtonBack')
        self.settings_button = self.findChild(QPushButton, 'pushButtonSettings')

        # Set up the channels model
        channel_file = self.settings.value('channel_file', 'channels.txt')
        self.channels_model = ChannelsModel(channel_file)
        self.channels_list.setModel(self.channels_model)

        # Load saved settings
        self.api_key_input.setText(self.settings.value('api_key', ''))
        self.output_dir_input.setText(self.settings.value('base_dir', ''))

        # Connect signals
        self.channels_list.clicked.connect(self.on_channel_selected)
        self.channels_list.doubleClicked.connect(self.show_download_dialog)
        self.reload_button.clicked.connect(self.reload_channels)
        self.back_button.clicked.connect(self.web_view.back)
        self.forward_button.clicked.connect(self.web_view.forward)
        self.download_button.clicked.connect(self.show_download_dialog)
        self.settings_button.clicked.connect(self.show_settings)

        self.web_view.urlChanged.connect(self.on_url_changed)
        # Make URL label clickable
        self.url_label.mouseDoubleClickEvent = self.on_url_label_double_click

    def on_url_changed(self, url):
        """Update URL label when web view URL changes"""
        self.url_label.setText(url.toString())

    def on_url_label_double_click(self, event):
        """Handle double click on URL label"""
        if event.button() == Qt.LeftButton:
            current_url = self.web_view.url().toString()

            # Check if this is a YouTube video URL
            if 'youtube.com/watch' in current_url:
                try:
                    # Get video metadata to get title
                    downloader = ChannelDownloader(
                        api_key=self.settings.value('api_key', ''),
                        output_dir=self.settings.value('base_dir', ''),
                        progress_callback=lambda x: None
                    )

                    metadata = downloader.get_video_metadata(current_url)

                    # Clean title for filename
                    clean_title = "".join(c for c in metadata.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    default_filename = f"{clean_title}.mp4"

                    # Get save location from user
                    save_path, _ = QFileDialog.getSaveFileName(
                        self,
                        "Save Video As",
                        os.path.join(self.settings.value('base_dir', ''), default_filename),
                        "Video Files (*.mp4)"
                    )

                    if save_path:
                        # Create and show download dialog
                        dialog = SingleVideoDownloadDialog(
                            url=current_url,
                            output_dir=os.path.dirname(save_path),
                            api_key=self.settings.value('api_key', ''),
                            parent=self
                        )
                        dialog.show()

                        # Start download in a separate thread
                        from threading import Thread
                        Thread(
                            target=dialog.download_video,
                            args=(save_path,),
                            daemon=True
                        ).start()

                        # Show dialog
                        dialog.exec_()

                except Exception as e:
                    import traceback
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to start download: {str(e)}\n{traceback.format_exc()}"
                    )

    def create_menu_bar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        # Settings action
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Reload channels with new settings
            channel_file = self.settings.value('channel_file', 'channels.txt')
            self.channels_model.load_channels(channel_file)
            # Update API key input
            self.api_key_input.setText(self.settings.value('api_key', ''))
            # Update output directory input
            self.output_dir_input.setText(self.settings.value('base_dir', ''))

    def show_download_dialog(self):
        channel = self.channels_model.data(self.channels_list.currentIndex(), 0)
        if not channel:
            return
        if "@" in channel:
            channel = channel.replace("@", "")
        api_key = self.settings.value('api_key', '')
        output_dir = self.settings.value('base_dir', '')
        max_threads = int(self.settings.value('max_threads', '4'))

        dialog = DownloadDialog(self)
        dialog.setup(api_key, channel, output_dir, max_threads)
        dialog.exec_()

    def on_channel_selected(self, index):
        channel = self.channels_model.data(index, 0)
        url = f"https://www.youtube.com/{channel}"
        self.web_view.setUrl(QUrl(url))
        self.url_label.setText(url)

    def reload_channels(self):
        channel_file = self.settings.value('channel_file', 'channels.txt')
        self.channels_model.load_channels(channel_file)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
