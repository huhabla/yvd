import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QFileDialog, QSpinBox, QComboBox
)
from PyQt5.QtCore import QSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('YVD', 'YoutubeVideoDownloader')
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.setWindowTitle("Settings")
        layout = QVBoxLayout()

        # Form layout for inputs
        form = QFormLayout()

        # Channel file settings
        self.channel_file = QLineEdit()
        self.channel_browse = QPushButton("Browse")
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(self.channel_file)
        channel_layout.addWidget(self.channel_browse)
        form.addRow("Channels File:", channel_layout)

        # API Key
        self.api_key = QLineEdit()
        form.addRow("YouTube API Key:", self.api_key)

        # Base directory
        self.base_dir = QLineEdit()
        self.dir_browse = QPushButton("Browse")
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.base_dir)
        dir_layout.addWidget(self.dir_browse)
        form.addRow("Base Directory:", dir_layout)

        # Max threads
        self.max_threads = QSpinBox()
        self.max_threads.setMinimum(1)
        self.max_threads.setMaximum(12)
        form.addRow("Max Download Threads:", self.max_threads)

        # Add resolution selector
        self.resolution_combo = QComboBox()
        # self.resolution_combo.addItems(['2160p', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p'])
        self.resolution_combo.addItems(['360p'])
        form.addRow("Preferred Resolution:", self.resolution_combo)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect signals
        self.channel_browse.clicked.connect(self.browse_channel_file)
        self.dir_browse.clicked.connect(self.browse_directory)
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)

    def browse_channel_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Channels File", "", "Text Files (*.txt)")
        if filename:
            self.channel_file.setText(filename)

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Base Directory")
        if directory:
            self.base_dir.setText(directory)

    def load_settings(self):
        self.channel_file.setText(
            self.settings.value('channel_file', 'channels.txt'))
        self.api_key.setText(
            self.settings.value('api_key', ''))
        self.base_dir.setText(
            self.settings.value('base_dir', os.path.expanduser('~')))
        self.max_threads.setValue(
            int(self.settings.value('max_threads', 4)))
        # Load resolution setting
        resolution = self.settings.value('preferred_resolution', '1080p')
        index = self.resolution_combo.findText(resolution)
        if index >= 0:
            self.resolution_combo.setCurrentIndex(index)

    def save_settings(self):
        self.settings.setValue('channel_file', self.channel_file.text())
        self.settings.setValue('api_key', self.api_key.text())
        self.settings.setValue('base_dir', self.base_dir.text())
        self.settings.setValue('max_threads', self.max_threads.value())
        self.settings.setValue('preferred_resolution', self.resolution_combo.currentText())
        self.accept()
