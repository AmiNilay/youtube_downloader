from flask import Flask, request, send_file, render_template, jsonify, Response
from yt_dlp import YoutubeDL
import os
import logging
import shutil
import glob
import secrets
import socket
import requests

app = Flask(__name__)

# Configure logging with more detail
logging.basicConfig(
    filename='error.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def check_internet_connection():
    """Check if the server has an active internet connection."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        requests.get("https://www.google.com", timeout=5)
        return True
    except (socket.error, requests.RequestException) as e:
        logging.error(f"Internet connection check failed: {str(e)}")
        return False

def sanitize_title(title):
    """Sanitize the title to create a valid filename."""
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return sanitized_title.strip('_')  # Remove leading and trailing underscores

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Index error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}. Please try again later."}), 500

@app.route('/help')
def help():
    try:
        return render_template('help.html')
    except Exception as e:
        logging.error(f"Help error: {str(e)}")
        return jsonify({'error': f"Server error: {str(e)}. Please try again later."}), 500

@app.route('/get_streams', methods=['POST'])
def get_streams():
    url = request.form['url']
    try:
        if not check_internet_connection():
            return jsonify({'error': 'Server has no internet connection. Please check your network and try again.'}), 503

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'format_sort': ['+size', '+br'],
            'extract_flat': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info or 'formats' not in info:
                    logging.error(f"No valid info extracted for URL {url}")
                    return jsonify({'error': 'Video not available. It might be private, deleted, or restricted.'}), 400
            except Exception as e:
                logging.error(f"Failed to extract info for URL {url}: {str(e)}")
                return jsonify({'error': f'Unable to access video. It might be private, deleted, or restricted: {str(e)}'}), 400

            streams = []
            seen_qualities = {}
            audio_streams = []
            video_streams = []

            for s in info.get('formats', []):
                if s.get('vcodec') == 'none' and s.get('acodec') == 'none':
                    continue
                quality = 'Audio' if s.get('vcodec') == 'none' and s.get('acodec') != 'none' else s.get('height')
                if quality is None or str(quality).lower() == 'none':
                    continue
                filesize = s.get('filesize') or s.get('filesize_approx')
                if filesize is None or filesize <= 0:
                    logging.warning(f"Filesize not available for format {s.get('format_id')}, estimating.")
                    filesize = 0
                size = filesize / 1048576 if filesize > 0 else 1

                format_id = s['format_id']
                stream_info = {
                    'format_id': format_id,
                    'quality': quality,
                    'size': size,
                    'format': 'mp3' if s.get('vcodec') == 'none' else 'mp4'
                }
                if s.get('vcodec') == 'none':
                    audio_streams.append(stream_info)
                else:
                    video_streams.append(stream_info)

            if audio_streams:
                audio_streams.sort(key=lambda x: x['size'], reverse=True)
                seen_qualities['Audio'] = audio_streams[0]

            if video_streams:
                for stream in video_streams:
                    quality = stream['quality']
                    if quality not in seen_qualities or stream['size'] > seen_qualities[quality]['size']:
                        seen_qualities[quality] = stream

            streams = list(seen_qualities.values())
            streams.sort(key=lambda x: (x['quality'] != 'Audio', x['quality'] or 0))

            if not streams:
                logging.warning(f"No downloadable streams found for URL {url}")
                return jsonify({'error': 'No downloadable streams found. The video might be live, restricted, or unavailable.'}), 400

            thumbnail_available = bool(info.get('thumbnail'))

            return jsonify({
                'streams': streams,
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'thumbnail_available': thumbnail_available
            })
    except Exception as e:
        logging.error(f"Stream fetch error for URL {url}: {str(e)}")
        return jsonify({'error': f"Failed to fetch streams: {str(e)}. Please try a different video."}), 500

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    format_id = request.form.get('format_id')
    stream_format = request.form.get('format')  # mp3 or mp4
    logging.info(f"Received download request: URL={url}, format_id={format_id}, stream_format={stream_format}")

    if not url or not format_id:
        logging.error("Missing URL or format ID")
        return jsonify({'error': 'URL or format ID missing'}), 400

    try:
        if not check_internet_connection():
            logging.error("No internet connection. Cannot proceed with download.")
            return jsonify({'error': 'Server has no internet connection. Please check your network and try again.'}), 503

        # Create downloads directory
        download_dir = 'downloads'
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
            os.chmod(download_dir, 0o777)  # Ensure the directory is writable
            logging.info(f"Created downloads directory: {download_dir}")

        # Define file paths
        temp_file_base = os.path.join(download_dir, f'temp_{format_id}_{secrets.token_hex(4)}')
        final_ext = 'mp3' if stream_format == 'mp3' else 'mp4'
        output_file = f"{temp_file_base}.{final_ext}"  # Final file path (e.g., temp_251_b1b1450f.mp3)
        temp_download_file = f"{temp_file_base}.%(ext)s"  # Temporary file path for yt-dlp (e.g., temp_251_b1b1450f.webm)
        logging.info(f"Temp download file path: {temp_download_file}")
        logging.info(f"Final output file path: {output_file}")

        # Check for FFmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            logging.error("FFmpeg not found in PATH")
            return jsonify({'error': 'FFmpeg is not installed or not found in PATH. Please install FFmpeg.'}), 500

        # Download hook for logging progress
        def download_hook(d):
            if d['status'] == 'finished':
                logging.info(f"Download finished: {d.get('filename')}")
            elif d['status'] == 'error':
                logging.error(f"Download error: {d.get('error')}")
            elif d['status'] == 'downloading':
                logging.debug(f"Downloading: {d.get('downloaded_bytes')} of {d.get('total_bytes')} bytes")

        # Configure yt-dlp options
        ydl_opts = {
            'outtmpl': temp_download_file,  # Use a temporary file path for initial download
            'format': 'bestaudio/best' if stream_format == 'mp3' else f'{format_id}+bestaudio/best',
            'ffmpeg_location': ffmpeg_path,
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4' if stream_format == 'mp4' else None,
            'prefer_ffmpeg': True,
            'noplaylist': True,
            'progress_hooks': [download_hook],
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'http_chunk_size': 10485760,
            'format_sort': ['+size', '+br'],
            'verbose': True,  # Enable verbose output for debugging
            'ignoreerrors': False,  # Do not ignore errors, so we can catch them
            'nooverwrites': True,  # Prevent overwriting existing files
        }

        # If downloading audio, let yt-dlp handle the conversion to MP3
        if stream_format == 'mp3':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        # Download the file
        with YoutubeDL(ydl_opts) as ydl:
            try:
                logging.info(f"Starting download for URL {url} with format {stream_format}")
                info = ydl.extract_info(url, download=True)
                if not info:
                    logging.error(f"No info returned after download for URL {url}")
                    return jsonify({'error': 'Failed to download video: No information returned. The video might be unavailable or restricted.'}), 400
                logging.info(f"Download completed for URL {url}")
            except Exception as e:
                logging.error(f"yt_dlp failed to download URL {url}: {str(e)}")
                if "Video unavailable" in str(e) or "Private video" in str(e) or "deleted" in str(e):
                    return jsonify({'error': f"Video is unavailable: {str(e)}. It might be private, deleted, or restricted."}), 400
                elif "network" in str(e).lower() or "connection" in str(e).lower():
                    return jsonify({'error': f"Network error during download: {str(e)}. Please check your internet connection and try again."}), 503
                elif "ffmpeg" in str(e).lower():
                    return jsonify({'error': f"FFmpeg error during conversion: {str(e)}. Please ensure FFmpeg is installed and in your PATH."}), 500
                else:
                    return jsonify({'error': f"Failed to download video: {str(e)}. Please try again or use a different video."}), 500

        # Handle the file after download
        actual_file = None
        if stream_format == 'mp3':
            # For MP3, yt-dlp appends .mp3 to the output file, so look for temp_251_b1b1450f.mp3.mp3
            possible_mp3_file = f"{temp_file_base}.mp3.mp3"
            logging.info(f"Looking for MP3 file: {possible_mp3_file}")
            if os.path.exists(possible_mp3_file):
                actual_file = possible_mp3_file
                logging.info(f"Found MP3 file: {actual_file}")
            else:
                # Check for other possible extensions in case something went wrong
                possible_files = glob.glob(f"{temp_file_base}.*")
                logging.error(f"MP3 file not found at {possible_mp3_file}. Available files: {possible_files}")
                all_files = os.listdir(download_dir)
                logging.debug(f"All files in downloads directory: {all_files}")
                return jsonify({'error': 'MP3 file not found after conversion. Please try again or use a different video.'}), 500

            # Rename the file to the expected output_file (e.g., temp_251_b1b1450f.mp3)
            logging.info(f"Renaming {actual_file} to {output_file}")
            os.rename(actual_file, output_file)
        else:
            # For MP4, the file should already be at output_file
            if os.path.exists(output_file):
                actual_file = output_file
                logging.info(f"Found MP4 file: {actual_file}")
            else:
                possible_files = glob.glob(f"{temp_file_base}.*")
                logging.error(f"MP4 file not found at {output_file}. Available files: {possible_files}")
                all_files = os.listdir(download_dir)
                logging.debug(f"All files in downloads directory: {all_files}")
                return jsonify({'error': 'MP4 file not found after download. Please try again or use a different video.'}), 500

        # Double-check the final file exists
        if not os.path.exists(output_file):
            logging.error(f"Final output file not found at {output_file}")
            all_files = os.listdir(download_dir)
            logging.debug(f"All files in downloads directory: {all_files}")
            return jsonify({'error': 'Final file not found after processing. Please try again or use a different video.'}), 500

        # Sanitize the final file name for the Content-Disposition header
        final_file_name = f"{sanitize_title(info['title'])}.{final_ext}"
        logging.info(f"Final file name for download: {final_file_name}")

        # Send the file to the client
        def generate():
            with open(output_file, 'rb') as f:
                while True:
                    chunk = f.read(1048576)  # Read in 1MB chunks
                    if not chunk:
                        break
                    yield chunk

        response = Response(
            generate(),
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{final_file_name}"',
                'Content-Length': str(os.path.getsize(output_file))
            }
        )

        @response.call_on_close
        def cleanup():
            try:
                for file in glob.glob(f"{temp_file_base}.*"):
                    if os.path.exists(file):
                        logging.info(f"Cleaning up file: {file}")
                        os.remove(file)
            except Exception as e:
                logging.error(f"Error cleaning up files for {temp_file_base}: {str(e)}")

        return response

    except Exception as e:
        logging.error(f"Download error for URL {url}: {str(e)}")
        for file in glob.glob(f"{temp_file_base}.*"):
            try:
                if os.path.exists(file):
                    logging.info(f"Cleaning up file on error: {file}")
                    os.remove(file)
            except Exception as e:
                logging.error(f"Error cleaning up temp file {file}: {str(e)}")
        return jsonify({'error': f"Unexpected error during download: {str(e)}. Please try again later."}), 500

@app.route('/download_extra', methods=['POST'])
def download_extra():
    url = request.form.get('url')
    file_type = request.form.get('type')

    if not url:
        logging.error("Missing URL")
        return jsonify({'error': 'URL missing'}), 400

    try:
        if not check_internet_connection():
            logging.error("No internet connection. Cannot proceed with download.")
            return jsonify({'error': 'Server has no internet connection. Please check your network and try again.'}), 503

        download_dir = 'downloads'
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
            os.chmod(download_dir, 0o777)  # Ensure the directory is writable

        temp_file_base = os.path.join(download_dir, f'temp_extra_{secrets.token_hex(4)}')
        thumbnail_file = f"{temp_file_base}.jpg"

        def download_hook(d):
            if d['status'] == 'finished':
                logging.info(f"Thumbnail download finished: {d.get('filename')}")
            elif d['status'] == 'error':
                logging.error(f"Thumbnail download error: {d.get('error')}")

        ydl_opts = {
            'outtmpl': f"{temp_file_base}.%(ext)s",
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'progress_hooks': [download_hook],
            'socket_timeout': 30,
            'retries': 10,
            'http_chunk_size': 10485760,
            'verbose': True,
        }

        if file_type == 'thumbnail':
            ydl_opts['writethumbnail'] = True
            ydl_opts['skip_download'] = True
        else:
            return jsonify({'error': 'Invalid file type'}), 400

        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                logging.error(f"yt_dlp failed to download {file_type} for URL {url}: {str(e)}")
                if "Video unavailable" in str(e) or "Private video" in str(e) or "deleted" in str(e):
                    return jsonify({'error': f"Video is unavailable: {str(e)}. It might be private, deleted, or restricted."}), 400
                elif "network" in str(e).lower() or "connection" in str(e).lower():
                    return jsonify({'error': f"Network error during download: {str(e)}. Please check your internet connection and try again."}), 503
                else:
                    return jsonify({'error': f"Failed to download {file_type}: {str(e)}."}), 500

        thumbnail_path = None
        for ext in ['jpg', 'webp']:
            possible_thumbnail = f"{temp_file_base}.{ext}"
            if os.path.exists(possible_thumbnail):
                thumbnail_path = possible_thumbnail
                break

        if not thumbnail_path:
            logging.error(f"Thumbnail file not found at {temp_file_base}.*")
            return jsonify({'error': 'Thumbnail not available for this video. It might be restricted or unavailable.'}), 404

        if thumbnail_path.endswith('.webp'):
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logging.error("FFmpeg not found in PATH")
                return jsonify({'error': 'FFmpeg is not installed or not found in PATH. Please install FFmpeg.'}), 500

            converted_thumbnail = f"{temp_file_base}.jpg"
            try:
                subprocess.run([
                    ffmpeg_path, '-i', thumbnail_path, converted_thumbnail
                ], check=True, capture_output=True, text=True)
                os.remove(thumbnail_path)
                thumbnail_path = converted_thumbnail
            except subprocess.CalledProcessError as e:
                logging.error(f"FFmpeg error converting thumbnail: {e.stderr}")
                return jsonify({'error': 'Failed to process thumbnail.'}), 500

        if not os.path.exists(thumbnail_path):
            logging.error(f"Thumbnail file not found at {thumbnail_path}")
            return jsonify({'error': 'Thumbnail not available for this video. It might be restricted or unavailable.'}), 404

        final_thumbnail_name = f"{sanitize_title(info['title'])}_thumbnail.jpg"

        def generate():
            with open(thumbnail_path, 'rb') as f:
                while True:
                    chunk = f.read(1048576)
                    if not chunk:
                        break
                    yield chunk

        response = Response(
            generate(),
            mimetype='image/jpeg',
            headers={
                'Content-Disposition': f'attachment; filename="{final_thumbnail_name}"',
                'Content-Length': str(os.path.getsize(thumbnail_path))
            }
        )

        @response.call_on_close
        def cleanup():
            try:
                for file in glob.glob(f"{temp_file_base}.*"):
                    if os.path.exists(file):
                        os.remove(file)
            except Exception as e:
                logging.error(f"Error cleaning up files for {temp_file_base}: {str(e)}")

        return response

    except Exception as e:
        logging.error(f"Download extra error for URL {url}: {str(e)}")
        for file in glob.glob(f"{temp_file_base}.*"):
            try:
                if os.path.exists(file):
                    os.remove(file)
            except Exception as e:
                logging.error(f"Error cleaning up temp file {file}: {str(e)}")
        return jsonify({'error': f"Server error during download: {str(e)}. Please try again later."}), 500

@app.route('/cancel', methods=['POST'])
def cancel():
    try:
        download_dir = 'downloads'
        if os.path.exists(download_dir):
            for filename in os.listdir(download_dir):
                file_path = os.path.join(download_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logging.error(f"Error removing file {file_path}: {str(e)}")
        return jsonify({'status': 'success', 'message': 'Download canceled and files cleaned up.'})
    except Exception as e:
        logging.error(f"Cancel error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def cleanup_downloads():
    download_dir = 'downloads'
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir, ignore_errors=True)
    os.makedirs(download_dir, exist_ok=True)
    os.chmod(download_dir, 0o777)  # Ensure the directory is writable

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    try:
        cleanup_downloads()
        app.run(debug=debug, host=host, port=port)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        raise