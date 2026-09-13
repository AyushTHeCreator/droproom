# DropRoom

A temporary browser-based file-sharing room for quickly moving files between devices.

**Open → Create → Scan → Send**

## Features

✅ No account required
✅ Room codes (6-digit)
✅ QR code joining
✅ Multiple connected devices
✅ Real-time file uploads/downloads
✅ Automatic file cleanup
✅ Mobile responsive
✅ Drag and drop support
✅ Progress tracking
✅ No external dependencies

## Use Case

> "I have a file on my phone and want to quickly move it to my laptop without USB, email, Telegram, Google Drive, or installing an app."

## Tech Stack

**Backend:**
- Python 3.8+
- Flask
- Flask-SocketIO
- SQLAlchemy
- SQLite

**Frontend:**
- HTML5
- CSS3
- Vanilla JavaScript
- Socket.IO Client

## Installation

### Prerequisites

Python 3.8 or higher

### Setup

1. **Clone the repository:**

```bash
git clone https://github.com/AyushTHeCreator/droproom.git
cd droproom
```

2. **Create virtual environment:**

```bash
python -m venv venv
```

3. **Activate virtual environment:**

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

4. **Install dependencies:**

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
python app.py
```

The server will start at `http://127.0.0.1:5000`

### Access from Another Device on Same Network

During development, find your computer's local IP:

**Linux/Mac:**
```bash
ifconfig
```

**Windows:**
```bash
ipconfig
```

Then access from another device on the same Wi-Fi:
```
http://<YOUR_IP>:5000
```

Example: `http://192.168.1.100:5000`

## Project Structure

```
droproom/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── models.py              # SQLAlchemy database models
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── .gitignore             # Git ignore rules
│
├── uploads/               # Temporary file storage (created at runtime)
│
├── templates/
│   ├── base.html          # Base template
│   ├── index.html         # Homepage
│   ├── join_room.html     # Join room form
│   ├── room.html          # Main room interface
│   └── error.html         # Error page
│
└── static/
    ├── css/
    │   └── style.css      # Application styles
    └── js/
        └── room.js        # Client-side logic
```

## How It Works

### 1. Room Creation

- User clicks "Create Room"
- Server generates a random 6-digit code
- Room is stored in SQLite with an expiration time (30 minutes by default)
- User receives room code and QR code

### 2. Device Connection

- Second device scans QR code or enters room code
- Browser connects via Socket.IO (WebSocket)
- Both devices see each other in real-time
- User can set a device name

### 3. File Sharing

- Files are uploaded to the server
- Server stores files in `uploads/<room_code>/`
- Each file gets a unique ID in the database
- Original filename is preserved
- All connected devices are notified via Socket.IO
- Files can be downloaded by any device in the room

### 4. Automatic Cleanup

- Background thread checks for expired rooms every minute
- Expired rooms:
  - Files deleted from disk
  - Database records removed
  - Connected clients disconnected
- Default expiration: 30 minutes of inactivity

## Database Schema

### Room
```
id (UUID)
code (unique 6-digit string)
created_at (timestamp)
last_activity (timestamp)
expires_at (timestamp)
```

### Device
```
id (UUID)
room_id (foreign key)
device_name (string)
session_id (unique)
joined_at (timestamp)
last_seen (timestamp)
```

### File
```
id (UUID)
room_id (foreign key)
device_id (foreign key)
original_filename (string)
stored_filename (string, unique)
file_size (integer)
mime_type (string)
uploaded_at (timestamp)
```

## Configuration

Edit `config.py` to customize:

```python
# Room settings
ROOM_CODE_LENGTH = 6                    # Digits in room code
ROOM_EXPIRY_MINUTES = 30                # Minutes until room expires
MAX_DEVICES_PER_ROOM = 10               # Max concurrent devices
DEVICE_HEARTBEAT_TIMEOUT = 5            # Minutes before device marked inactive

# File upload
MAX_UPLOAD_SIZE_MB = 100                # Max file size
ALLOWED_EXTENSIONS = {...}              # Allowed file types

# Cleanup
CLEANUP_CHECK_INTERVAL_SECONDS = 60     # How often to check for expired rooms
```

## Socket.IO Events

### Client → Server

- `join_room` - Device joins a room
- `heartbeat` - Keep connection alive
- `disconnect` - Device leaves

### Server → Client

- `devices_updated` - List of connected devices changed
- `device_joined` - New device joined
- `device_left` - Device disconnected
- `file_uploaded` - New file available
- `file_deleted` - File was deleted
- `room_expired` - Room has expired
- `error` - Error occurred

## REST API Endpoints

### GET `/`
Homepage

### POST `/create-room`
Create new room
```json
Response: { "room_code": "482913", "join_url": "..." }
```

### GET `/join`
Join room form

### POST `/join`
Submit room code

### GET `/join/<room_code>`
Direct join via URL (QR code)

### GET `/room/<room_code>`
Room interface page

### POST `/room/<room_code>/upload`
Upload file to room
- Form data: `file`, `device_id`

### GET `/room/<room_code>/download/<file_id>`
Download file from room

### DELETE `/room/<room_code>/file/<file_id>`
Delete file from room

### GET `/room/<room_code>/files`
Get all files in room

### GET `/room/<room_code>/devices`
Get all devices in room

## Testing

### Test 1: Create and Join
1. Open browser on Device A → `http://localhost:5000`
2. Click "Create Room" → note the 6-digit code
3. Open second browser on Device B → `http://localhost:5000`
4. Click "Join Room" → enter the code
5. ✅ Both devices should see each other in real-time

### Test 2: Upload File
1. Device A: Drag and drop a file into the upload area
2. Device B: See the file appear without refreshing
3. ✅ File details shown (name, size, uploader)

### Test 3: Download File
1. Device A: Upload a PDF
2. Device B: Click "Download"
3. ✅ File downloads with original filename

### Test 4: Delete File
1. Device A: Upload an image
2. Device B: Click "Delete" on the file
3. Device A: File disappears in real-time
4. ✅ Both devices synchronized

### Test 5: Room Expiration
1. Create a room
2. Wait 30+ minutes without activity
3. ✅ Room expires, files deleted, clients disconnected

### Test 6: Error Handling
1. Try invalid room code → "Room not found"
2. Try uploading file larger than limit → "File exceeds 100MB"
3. Try accessing room from another device after expiration → "Room not found"
4. ✅ Friendly error messages shown

### Test 7: Mobile Responsiveness
1. Open on Android/iPhone
2. ✅ UI scales properly
3. ✅ Upload button is large and easy to tap
4. ✅ Files stack vertically

### Test 8: File Type Support
Upload these file types:
- PDF ✅
- Images (JPG, PNG) ✅
- Documents (DOCX, PPTX, XLSX) ✅
- Video (MP4, WebM) ✅
- Archives (ZIP) ✅
- Text (TXT, CSV, JSON) ✅

## Security Considerations

✅ Room codes are random (not sequential)
✅ File names sanitized with `secure_filename`
✅ Path traversal prevented
✅ Upload size limited to 100MB
✅ Session-based device tracking
✅ Room-scoped file access
✅ No external authentication needed (stateless)

**For Production:**
- Use HTTPS
- Set `SECRET_KEY` environment variable
- Use PostgreSQL instead of SQLite
- Deploy to secure server
- Consider rate limiting
- Add CORS security headers
- Use environment variables for config

## Future Enhancements

### WebRTC/P2P Transfer

The current architecture is designed to easily add P2P file transfers:

1. **Signal via Socket.IO**: Use existing Socket.IO connection to exchange WebRTC offer/answer
2. **Data Channels**: Use WebRTC data channels for direct device-to-device transfer
3. **Server Relay Fallback**: Keep server as fallback if P2P fails
4. **Progressive Enhancement**: Try P2P first, fall back to server

Implementation hints:
- Add P2P negotiation in `room.js`
- Keep server upload/download as fallback
- No breaking changes to existing code
- Database schema already supports future metadata

### Other Ideas
- Text message chat
- Link preview generation
- File search/filtering
- Device detection (phone/laptop/tablet)
- Custom room expiration time
- OAuth integration
- File encryption
- Usage analytics

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### Port 5000 already in use
```bash
# Edit app.py, change port parameter
socketio.run(app, port=5001)
```

### Files not uploading
- Check file size < 100MB
- Check file extension in `config.py`
- Check `uploads/` folder has write permissions
- Check browser console for errors

### Cannot access from another device
- Ensure both on same Wi-Fi network
- Check firewall isn't blocking port 5000
- Use local IP not `localhost`
- Disable VPN if on one

## License

MIT License - Feel free to use and modify

## Contributing

Contributions welcome! Submit issues and pull requests.

---

**Made with ❤️ for quick file sharing**
