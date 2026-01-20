# qBitHook

A REST API service that handles post-download actions for qBittorrent based on torrent categories.

## Features

- **Books Category**: 
  - Emails ebook files (azw3, epub, mobi) to your Kindle
  - Creates hardlinks for audiobook files (m4b, mp3) to a specified directory
  - Prioritizes azw3 > epub > mobi when multiple formats exist

- **Music Category**:
  - Sends webhook to [Fertilizer](https://github.com/moleculekayak/fertilizer) with torrent infohash

## Installation

### Docker-Compose
```
services:
  qbithook:
    container_name: qbithook
    image: ghcr.io/choff3/qbithook:latest
    restart: unless-stopped
    volumes:
      - <qBittorrent save directory>:/torrents
      - <qBitHook config directory>:/config
    ports:
      - 5338:5338
```

### Python
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the service by editing `config.json`:
   - Set up email settings (SMTP server, credentials)
   - Configure books category name and email recipient (e.g., Kindle email address)
   - Configure music category name and webhook endpoint
   - Set audio directory path for m4b files

3. Run the service:
```bash
python app.py
```

The API will start on `http://0.0.0.0:5338`

## Configuration

Edit `config.json` with your settings:

```json
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": true,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "from_address": "your-email@gmail.com"
  },
  "books": {
    "category": "books",
    "email_recipient": "kindle-email@kindle.com",
    "audio_directory": "/path/to/audiobooks"
  },
  "music": {
    "category": "lidarr",
    "fertilizer_endpoint": "http://fertilizer:9713/api/webhook"
  }
}
```

### Email Setup for Gmail

If using Gmail, you'll need to:
1. Enable 2-factor authentication
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Use the App Password in the config file

## qBittorrent Setup

1. Go to qBittorrent Settings → Downloads → Run external program on torrent completion

2. Enable "Run external program on torrent finished"

3. Add the following command (adjust the URL to your API server):
```bash
curl -X POST http://localhost:5338/webhook -d "name=%N" -d "category=%L" -d "tags=%G" -d "content_path=%F" -d "root_path=%R" -d "save_path=%D" -d "num_files=%C" -d "size=%Z" -d "tracker=%T" -d "infohash_v1=%I" -d "infohash_v2=%J" -d "torrent_id=%K"
```

## API Endpoints

### POST /webhook
Handles qBittorrent post-download webhook calls.

**Expected Form Parameters:**
- `name`: Torrent name (%N)
- `category`: Category (%L)
- `content_path`: Content path (%F)
- `infohash_v1`: Info hash v1 (%I)
- (and other qBittorrent parameters)

**Response:**
```json
{
  "status": "success|error",
  "message": "Processing details",
  "torrent_name": "Example Torrent",
  "category": "books"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

## Logging

The service logs all actions to stdout with timestamps. Monitor logs to troubleshoot any issues:

```bash
python app.py 2>&1 | tee qbithook.log
```

## Troubleshooting

- **Email not sending**: Check SMTP credentials and ensure less secure app access or app passwords are configured
- **Hardlink fails**: Ensure source and destination are on the same filesystem
- **Webhook fails**: Check network connectivity to the fertilizer server and verify the endpoint URL