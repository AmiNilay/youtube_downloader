# YouTube Downloader

A web application that allows you to download YouTube videos as MP4 or audio as MP3 directly from your browser.

## For End-Users: Using the Web App

This app is hosted online, and you can use it directly in your browser without any setup. Simply visit the following URL to start downloading YouTube videos or audio:

🔗 **[Use the App Here]([Link to be added after deployment])**

### How to Use
1. Open the app in your browser using the link above.
2. Enter a YouTube URL (e.g., `https://www.youtube.com/watch?v=17vlZqtNIOc`).
3. Select a stream:
   - Choose "Audio (mp3)" to download the audio as an MP3 file.
   - Choose a video resolution (e.g., "360") to download the video as an MP4 file.
4. Click "Download" to start the download.
5. You can also download the video thumbnail by selecting the "Thumbnail" option.

### Troubleshooting for Users
- **Video Unavailable**: Some videos may be private, deleted, or restricted (e.g., region-locked or age-restricted). Try a different video.
- **Download Fails**: Ensure your internet connection is stable. If the issue persists, report it via GitHub Issues (see "Contributing" below).
- **Test Video**: Try a publicly available video like `https://www.youtube.com/watch?v=dQw4w9WgXcQ` to test the app.


## For Developers: Modifying or Running the Code Locally

If you’re a developer who wants to modify this app, contribute to it, or run it locally on your machine, follow the instructions below.

### Features
- Download YouTube videos in MP4 format.
- Extract and download audio from YouTube videos in MP3 format.
- Download video thumbnails.
- User-friendly web interface with error handling and feedback.

### Prerequisites
- **Python 3.6+**: Ensure Python is installed on your system.
- **FFmpeg**: Required for MP3 conversion. Install it and add it to your system PATH.
  - **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.
  - **Linux**: Run `sudo apt install ffmpeg`.
  - **macOS**: Run `brew install ffmpeg`.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/youtube-downloader.git
   cd youtube-downloader
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure FFmpeg is installed and accessible:
   ```bash
   ffmpeg -version
   ```
   If this command fails, install FFmpeg and add it to your PATH.

### Usage
1. Run the Flask app:
   ```bash
   python app.py
   ```
2. Open your browser and go to `http://127.0.0.1:5000`.
3. Enter a YouTube URL, select a stream (e.g., Audio (mp3) or a video resolution), and click "Download".

### Deployment
To host this app online (e.g., on Render, Heroku, or a VPS), follow these steps:
1. Ensure `requirements.txt` is included in your repository.
2. Use a platform like Render:
   - Create a new Web Service on Render and connect your GitHub repository.
   - Set the runtime to Python.
   - Add a build command: `pip install -r requirements.txt`.
   - Add a start command: `gunicorn app:app`.
   - Note: You may need to include FFmpeg in your deployment. For Render, use a `Dockerfile` like this:
     ```dockerfile
     FROM python:3.9-slim

     # Install FFmpeg
     RUN apt-get update && apt-get install -y ffmpeg

     # Set working directory
     WORKDIR /app

     # Copy project files
     COPY . .

     # Install Python dependencies
     RUN pip install -r requirements.txt

     # Expose port
     EXPOSE 5000

     # Run the app
     CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

3. Once deployed, update this `README.md` with the live URL in the "For End-Users" section.

### Troubleshooting for Developers
- **FFmpeg Not Found**: If you see an error about FFmpeg, ensure it’s installed and in your PATH.
- **Video Unavailable**: Some videos may require a GVS PO Token due to YouTube restrictions. See [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) for more information.
- **Logs**: Check `error.log` in the project directory for detailed error messages.
- **Dependencies**: Ensure all dependencies are installed as per `requirements.txt`.

### Project Structure
- `app.py`: The main Flask application.
- `templates/index.html`: The web interface.
- `requirements.txt`: Python dependencies.
- `.gitignore`: Excludes temporary files like `downloads/` and `error.log`.
- `Dockerfile` (optional): For deploying on platforms like Render that require FFmpeg.

## Contributing
Whether you’re an end-user reporting an issue or a developer contributing code, we welcome your input! Please:
- Submit bug reports or feature requests via [GitHub Issues](https://github.com/your-username/youtube-downloader/issues).
- Fork the repository, make changes, and submit a pull request to contribute code.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built with [Flask](https://flask.palletsprojects.com/) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).
- Thanks to the open-source community for their amazing tools!
