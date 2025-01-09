# YVD - YouTube Video Downloader

A PyQt5-based desktop application for downloading complete YouTube channels with metadata. The application provides a
user-friendly interface to manage YouTube channel downloads, view channel content, and configure download settings.

## Features

- Browse YouTube channels in an integrated web view
- Download complete YouTube channels with metadata
- Configure preferred video resolution
- Multi-threaded downloads for better performance
- Save channel and video metadata
- Resume interrupted downloads
- Visual feedback for downloaded/pending videos
- Configurable download settings (API key, output directory, threads)
- Channel list management

## Prerequisites

- Python 3.8 or higher
- YouTube Data API v3 key ([Get it here](https://console.cloud.google.com/apis/library/youtube.googleapis.com))
- Git (for cloning the repository)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/huhabla/yvd.git
cd yvd
```

2. Create and activate a virtual environment:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python -m venv venv
source venv/bin/activate
```

3. Install required packages:

```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `channels.txt` file in the application directory with YouTube channel handles (one per line):

```
joerogan
veritasium
```

2. Launch the application:

```bash
python main.py
```

3. Open Settings from the File menu and configure:
    - YouTube API Key
    - Output Directory
    - Preferred Resolution
    - Maximum Download Threads
    - Channels File Location

## Usage

1. **Browse Channels**
    - Select a channel from the left sidebar
    - Use the integrated web view to browse channel content
    - Use back/forward buttons for navigation

2. **Download Videos**
    - Select a channel
    - Click "Download/Update" button
    - In the download dialog:
        - Click "List Videos" to fetch video list
        - Click "Start Download" to begin downloading
        - Monitor progress in the output window
        - View video metadata in the metadata pane

3. **Monitor Progress**
    - Green items: Already downloaded
    - Red items: Pending download
    - Progress messages in output window

## Features in Detail

- **Multi-threaded Downloads**: Configurable number of simultaneous downloads
- **Resolution Selection**: Choose preferred video quality
- **Metadata Storage**: Saves video information in JSON format
- **Download Resume**: Continues from last successful download
- **Progress Tracking**: Visual feedback for download status
- **Channel Management**: Easy addition/removal of channels
- **Settings Persistence**: Saves configuration between sessions

## File Structure

- `main.py`: Application entry point
- `main_window.ui`: Main interface layout
- `download_dialog.ui`: Download manager layout
- `channel_downloader.py`: Core download functionality
- `settings_dialog.py`: Settings management
- `channels.txt`: Channel list

## Dependencies

- PyQt5: GUI framework
- PyTubeFix: YouTube download engine
- Google API Client: YouTube Data API interface
- Pydantic: Data validation

## Notes

- Requires a valid YouTube Data API key
- Respects YouTube's terms of service
- Downloads are saved in channel-specific folders
- Metadata is stored alongside videos
- Internet connection required

## Troubleshooting

1. **API Key Issues**
    - Verify key in settings
    - Check API quota limits
    - Ensure API is enabled in Google Console

2. **Download Failures**
    - Check internet connection
    - Verify output directory permissions
    - Check available disk space

3. **Performance Issues**
    - Adjust maximum threads in settings
    - Close other resource-intensive applications
    - Check system resources
