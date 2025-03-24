from flask import Flask, request, send_file, jsonify
from yt_dlp import YoutubeDL
import os
import logging
import secrets
import shutil
import glob

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='error.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def sanitize_title(title):
    """Sanitize the title to create a valid filename."""
    sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return sanitized_title.strip('_')

def check_internet_connection():
    """Check if the server has an active internet connection."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception as e:
        logging.error(f"Internet connection check failed: {str(e)}")
        return False

@app.route('/')
def index():
    try:
        return "Welcome to YouTube Downloader Backend"
    except Exception as e:
        logging.error(f"Index error: {str(e)}")
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
            info = ydl.extract_info(url, download=False)
            if not info or 'formats' not in info:
                logging.error(f"No valid info extracted for URL {url}")
                return jsonify({'error': 'Video not available. It might be private, deleted, or restricted.'}), 400
            
            streams = []
            seen_qualities = {}
            audio_streams = []
            video_streams = []
            
            for s in info.get('formats', []):
                if s.get('vcodec') == 'none' and s.get('acodec') == 'none':
                    continue
                
                quality = 'Audio' if s.get('vcodec') == 'none' else s.get('height')
                if quality is None or str(quality).lower() == 'none':
                    continue
                
                filesize = s.get('filesize') or s.get('filesize_approx')
                size = filesize / 1048576 if filesize > 0 else 1
                
                stream_info = {
                    'format_id': s['format_id'],
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
        
        download_dir = 'downloads'
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
            os.chmod(download_dir, 0o777)
        
        temp_file_base = os.path.join(download_dir, f'temp_{format_id}_{secrets.token_hex(4)}')
        final_ext = 'mp3' if stream_format == 'mp3' else 'mp4'
        output_file = f"{temp_file_base}.{final_ext}"
        temp_download_file = f"{temp_file_base}.%(ext)s"
        
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            logging.error("FFmpeg not found in PATH")
            return jsonify({'error': 'FFmpeg is not installed or not found in PATH. Please install FFmpeg.'}), 500
        
        ydl_opts = {
            'outtmpl': temp_download_file,
            'ffmpeg_location': ffmpeg_path,
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'merge_output_format': 'mp4' if stream_format == 'mp4' else None,
            'verbose': True,
            'ignoreerrors': False,
            'nooverwrites': True,
        }
        
        if stream_format == 'mp3':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
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
                return jsonify({'error': f"Failed to download video: {str(e)}. Please try again or use a different video."}), 500
        
        actual_file = None
        if stream_format == 'mp3':
            possible_mp3_file = f"{temp_file_base}.mp3.mp3"
            if os.path.exists(possible_mp3_file):
                actual_file = possible_mp3_file
            else:
                possible_files = glob.glob(f"{temp_file_base}.*")
                logging.error(f"MP3 file not found at {possible_mp3_file}. Available files: {possible_files}")
                return jsonify({'error': 'MP3 file not found after conversion. Please try again or use a different video.'}), 500
        else:
            if os.path.exists(output_file):
                actual_file = output_file
            else:
                possible_files = glob.glob(f"{temp_file_base}.*")
                logging.error(f"MP4 file not found at {output_file}. Available files: {possible_files}")
                return jsonify({'error': 'MP4 file not found after download. Please try again or use a different video.'}), 500
        
        final_file_name = f"{sanitize_title(info['title'])}.{final_ext}"
        response = send_file(actual_file, as_attachment=True, download_name=final_file_name)
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
        logging.error(f"Download error for URL {url}: {str(e)}")
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
            os.chmod(download_dir, 0o777)
        
        temp_file_base = os.path.join(download_dir, f'temp_extra_{secrets.token_hex(4)}')
        thumbnail_file = f"{temp_file_base}.jpg"
        
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            logging.error("FFmpeg not found in PATH")
            return jsonify({'error': 'FFmpeg is not installed or not found in PATH. Please install FFmpeg.'}), 500
        
        ydl_opts = {
            'outtmpl': f"{temp_file_base}.%(ext)s",
            'writethumbnail': True,
            'skip_download': True,
            'ffmpeg_location': ffmpeg_path,
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'verbose': True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                logging.error(f"yt_dlp failed to download thumbnail for URL {url}: {str(e)}")
                return jsonify({'error': f"Failed to download thumbnail: {str(e)}. Please try again or use a different video."}), 500
        
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
        
        final_thumbnail_name = f"{sanitize_title(info['title'])}_thumbnail.jpg"
        response = send_file(thumbnail_path, as_attachment=True, download_name=final_thumbnail_name)
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
        return jsonify({'error': f"Server error during download: {str(e)}. Please try again later."}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host=host, port=port)
