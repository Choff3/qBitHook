from flask import Flask, request, jsonify
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import json
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration
def load_config():
    """Load configuration from config.json"""
    # Try multiple config locations
    config_paths = [
        Path(__file__).parent / 'config.json',
        Path('/config/config.json')
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    logger.info(f"Loading config from: {config_path}")
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing config file at {config_path}: {e}")
                raise
    
    # No config found
    logger.error(f"Config file not found. Searched locations: {[str(p) for p in config_paths]}")
    raise FileNotFoundError("config.json not found in any expected location")

CONFIG = load_config()

def send_email_with_attachment(filepath, recipient):
    """Send email with ebook attachment"""
    try:
        msg = MIMEMultipart()
        msg['From'] = CONFIG['email']['from_address']
        msg['To'] = recipient
        msg['Subject'] = f"eBook: {Path(filepath).name}"
        
        # Attach the file
        with open(filepath, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={Path(filepath).name}'
        )
        msg.attach(part)
        
        # Send email
        with smtplib.SMTP(CONFIG['email']['smtp_server'], CONFIG['email']['smtp_port']) as server:
            if CONFIG['email'].get('use_tls', True):
                server.starttls()
            if CONFIG['email'].get('username') and CONFIG['email'].get('password'):
                server.login(CONFIG['email']['username'], CONFIG['email']['password'])
            server.send_message(msg)
        
        logger.info(f"Successfully sent email with attachment: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def find_audiobook_file(content_path):
    """Find audiobook files (m4b or mp3)"""
    path = Path(content_path)
    audiobook_files = []
    
    # If it's a file, return it if it's a supported format
    if path.is_file():
        if path.suffix.lower() in ['.m4b', '.mp3']:
            return [str(path)]
        return []
    
    # If it's a directory, search for all audiobook files
    if path.is_dir():
        for ext in ['.m4b', '.mp3']:
            for file in path.rglob(f'*{ext}'):
                audiobook_files.append(str(file))
    
    return audiobook_files

def find_ebook_file(content_path):
    """Find epub file"""
    path = Path(content_path)
    
    # If it's a file, return it if it's a supported format
    if path.is_file():
        if path.suffix.lower() in ['.epub']:
            return str(path)
        return None
    
    # If it's a directory, search for files with priority
    if path.is_dir():
        for ext in ['.epub']:
            for file in path.rglob(f'*{ext}'):
                return str(file)
    
    return None

def create_hardlink(source, dest_dir):
    """Create a hardlink for audio files"""
    try:
        source_path = Path(source)
        dest_dir_path = Path(dest_dir)
        
        # Ensure destination directory exists
        dest_dir_path.mkdir(parents=True, exist_ok=True)
        
        dest_path = dest_dir_path / source_path.name
        
        # Create hardlink
        os.link(source, dest_path)
        logger.info(f"Created hardlink: {source} -> {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create hardlink: {e}")
        return False

def handle_books_category(content_path):
    """Handle books category downloads"""
    logger.info(f"Processing books download: {content_path}")
    
    path = Path(content_path)
    
    # Check for ebook files
    if path.is_file() and path.suffix.lower() in ['.epub']:
        ebook_file = str(path)
    elif path.is_dir():
        ebook_file = find_ebook_file(content_path)
    else:
        ebook_file = None
    
    if ebook_file:
        recipient = CONFIG['books']['email_recipient']
        return send_email_with_attachment(ebook_file, recipient)
    
    # Check for audiobook files (m4b or mp3)
    audiobook_files = find_audiobook_file(content_path)
    if audiobook_files:
        dest_dir = CONFIG['books']['audio_directory']
        success_count = 0
        for audio_file in audiobook_files:
            if create_hardlink(audio_file, dest_dir):
                success_count += 1
        
        if success_count > 0:
            logger.info(f"Successfully created {success_count}/{len(audiobook_files)} hardlinks")
            return True
        else:
            logger.error(f"Failed to create any hardlinks for {len(audiobook_files)} files")
            return False
    
    logger.warning(f"No supported file found in: {content_path}")
    return False

def handle_music_category(infohash):
    """Handle music category downloads"""
    logger.info(f"Processing music download with infohash: {infohash}")
    
    try:
        webhook_url = f"{CONFIG['music']['nemorosa_endpoint']}/api/webhook?infohash={infohash}"
        data = {'infohash': infohash}
        
        response = requests.post(webhook_url, data=data, timeout=10)
        response.raise_for_status()
        
        logger.info(f"nemorosa Success: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"nemorosa Failed: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle qBittorrent webhook"""
    try:
        # Get parameters from form data
        torrent_name = request.form.get('name', '')
        category = request.form.get('category', '')
        tags = request.form.get('tags', '')
        content_path = request.form.get('content_path', '')
        root_path = request.form.get('root_path', '')
        save_path = request.form.get('save_path', '')
        num_files = request.form.get('num_files', '')
        size = request.form.get('size', '')
        tracker = request.form.get('tracker', '')
        infohash_v1 = request.form.get('infohash_v1', '')
        infohash_v2 = request.form.get('infohash_v2', '')
        torrent_id = request.form.get('torrent_id', '')
        
        logger.info(f"Received webhook for torrent: {torrent_name}, category: {category}")
        
        success = False
        message = ""
        
        # Route based on category from config
        books_category = CONFIG.get('books', {}).get('category', '')
        music_category = CONFIG.get('music', {}).get('category', '')
        
        if category == books_category:
            success = handle_books_category(content_path)
            message = "Books processing completed"
        elif category == music_category:
            success = handle_music_category(infohash_v1)
            message = "Music webhook sent"
        else:
            message = f"Unknown category: {category}"
            logger.warning(message)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': message,
            'torrent_name': torrent_name,
            'category': category
        }), 200 if success else 500
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5338, debug=False)
