from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime, timedelta
import os
import uuid
import string
import random
import threading
import time
from functools import wraps

from config import Config
from models import db, Room, Device, File


# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=Config.MAX_UPLOAD_SIZE_BYTES + 1024 * 1024)

# Initialize database
db.init_app(app)

# Create upload folder if it doesn't exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_room_code():
    """Generate a random 6-digit room code"""
    return ''.join(random.choices(string.digits, k=Config.ROOM_CODE_LENGTH))


def get_unique_room_code():
    """Generate a unique room code"""
    while True:
        code = generate_room_code()
        if not Room.query.filter_by(code=code).first():
            return code


def get_file_icon(mime_type):
    """Return an emoji icon based on file type"""
    if mime_type.startswith('image'):
        return '🖼️'
    elif mime_type.startswith('video'):
        return '🎬'
    elif mime_type.startswith('audio'):
        return '🎵'
    elif 'pdf' in mime_type:
        return '📕'
    elif 'word' in mime_type or 'document' in mime_type:
        return '📄'
    elif 'sheet' in mime_type or 'excel' in mime_type:
        return '📊'
    elif 'presentation' in mime_type or 'powerpoint' in mime_type:
        return '📑'
    elif 'zip' in mime_type or 'rar' in mime_type or 'compress' in mime_type:
        return '📦'
    else:
        return '📄'


def format_file_size(size_bytes):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def get_room_or_404(room_code):
    """Helper to get room or return None"""
    room = Room.query.filter_by(code=room_code).first()
    if not room or room.is_expired():
        return None
    return room


def require_valid_room(f):
    """Decorator to check if room is valid"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        room_code = kwargs.get('room_code')
        room = get_room_or_404(room_code)
        if not room:
            return jsonify({'error': 'Room not found or expired'}), 404
        kwargs['room'] = room
        return f(*args, **kwargs)
    return decorated_function


def cleanup_expired_rooms():
    """Background task to clean up expired rooms"""
    with app.app_context():
        while True:
            try:
                expired_rooms = Room.query.filter(Room.expires_at < datetime.utcnow()).all()
                for room in expired_rooms:
                    # Delete all files associated with the room
                    room_upload_path = os.path.join(Config.UPLOAD_FOLDER, room.code)
                    if os.path.exists(room_upload_path):
                        import shutil
                        shutil.rmtree(room_upload_path)
                    
                    # Delete room from database (cascade deletes devices and files)
                    db.session.delete(room)
                
                db.session.commit()
                print(f"[Cleanup] Removed {len(expired_rooms)} expired rooms")
                
            except Exception as e:
                print(f"[Cleanup Error] {e}")
            
            # Check every minute
            time.sleep(Config.CLEANUP_CHECK_INTERVAL_SECONDS)


# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Homepage"""
    return render_template('index.html')


@app.route('/create-room', methods=['POST'])
def create_room():
    """Create a new room"""
    room_code = get_unique_room_code()
    
    expires_at = datetime.utcnow() + timedelta(minutes=Config.ROOM_EXPIRY_MINUTES)
    room = Room(
        code=room_code,
        expires_at=expires_at
    )
    
    db.session.add(room)
    db.session.commit()
    
    return jsonify({
        'room_code': room_code,
        'room_id': room.id,
        'join_url': f"{request.host_url.rstrip('/')}/join/{room_code}"
    })


@app.route('/join', methods=['GET', 'POST'])
def join():
    """Join room by code"""
    if request.method == 'POST':
        room_code = request.form.get('room_code', '').strip()
        room = get_room_or_404(room_code)
        
        if not room:
            return render_template('join_room.html', error='Room not found or expired'), 404
        
        return redirect(url_for('room', room_code=room_code))
    
    return render_template('join_room.html')


@app.route('/join/<room_code>')
def join_by_code(room_code):
    """Join via URL (from QR code)"""
    room = get_room_or_404(room_code)
    if not room:
        return render_template('error.html', error='Room not found or expired'), 404
    
    return redirect(url_for('room', room_code=room_code))


@app.route('/room/<room_code>')
def room(room_code):
    """Room page"""
    room = get_room_or_404(room_code)
    if not room:
        return render_template('error.html', error='Room not found or expired'), 404
    
    return render_template('room.html', room_code=room_code, max_upload_mb=Config.MAX_UPLOAD_SIZE_MB)


@app.route('/room/<room_code>/upload', methods=['POST'])
@require_valid_room
def upload_file(room_code, room):
    """Upload a file to the room"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    device_id = request.form.get('device_id')
    
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > Config.MAX_UPLOAD_SIZE_BYTES:
        return jsonify({'error': f'File exceeds {Config.MAX_UPLOAD_SIZE_MB}MB limit'}), 413
    
    # Verify device belongs to room
    device = Device.query.filter_by(id=device_id, room_id=room.id).first()
    if not device:
        return jsonify({'error': 'Device not found in room'}), 403
    
    # Update room activity
    room.update_activity()
    
    # Create room upload directory
    room_upload_path = os.path.join(Config.UPLOAD_FOLDER, room.code)
    os.makedirs(room_upload_path, exist_ok=True)
    
    # Generate unique filename
    original_filename = secure_filename(file.filename)
    stored_filename = f"{uuid.uuid4()}_{original_filename}"
    filepath = os.path.join(room_upload_path, stored_filename)
    
    # Save file
    file.save(filepath)
    
    # Create file record
    file_record = File(
        room_id=room.id,
        device_id=device.id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_size=file_size,
        mime_type=file.content_type or 'application/octet-stream'
    )
    
    db.session.add(file_record)
    db.session.commit()
    
    # Emit socket event to all clients in room
    file_data = file_record.to_dict()
    file_data['icon'] = get_file_icon(file_record.mime_type)
    file_data['formatted_size'] = format_file_size(file_size)
    
    socketio.emit('file_uploaded', file_data, room=room.code, namespace='/')
    
    return jsonify({'file_id': file_record.id, 'message': 'File uploaded successfully'}), 201


@app.route('/room/<room_code>/download/<file_id>')
@require_valid_room
def download_file(room_code, file_id, room):
    """Download a file from the room"""
    file_record = File.query.filter_by(id=file_id, room_id=room.id).first()
    
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    
    room.update_activity()
    
    filepath = os.path.join(Config.UPLOAD_FOLDER, room.code, file_record.stored_filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found on disk'}), 404
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=file_record.original_filename
    )


@app.route('/room/<room_code>/file/<file_id>', methods=['DELETE'])
@require_valid_room
def delete_file(room_code, file_id, room):
    """Delete a file from the room"""
    file_record = File.query.filter_by(id=file_id, room_id=room.id).first()
    
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    
    room.update_activity()
    
    # Delete file from disk
    filepath = os.path.join(Config.UPLOAD_FOLDER, room.code, file_record.stored_filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Delete from database
    db.session.delete(file_record)
    db.session.commit()
    
    # Emit socket event
    socketio.emit('file_deleted', {'file_id': file_id}, room=room.code, namespace='/')
    
    return jsonify({'message': 'File deleted'}), 200


@app.route('/room/<room_code>/files')
@require_valid_room
def get_files(room_code, room):
    """Get all files in the room"""
    files = File.query.filter_by(room_id=room.id).all()
    
    files_data = []
    for file_record in files:
        file_data = file_record.to_dict()
        file_data['icon'] = get_file_icon(file_record.mime_type)
        file_data['formatted_size'] = format_file_size(file_record.file_size)
        files_data.append(file_data)
    
    return jsonify(files_data), 200


@app.route('/room/<room_code>/devices')
@require_valid_room
def get_devices(room_code, room):
    """Get all devices in the room"""
    devices = Device.query.filter_by(room_id=room.id).all()
    devices_data = [device.to_dict() for device in devices]
    return jsonify(devices_data), 200


# ============================================================================
# SOCKET.IO EVENTS
# ============================================================================

@socketio.on('join_room')
def handle_join_room(data):
    """Handle device joining a room"""
    room_code = data.get('room_code')
    device_name = data.get('device_name', 'Unknown Device').strip()[:100]
    session_id = request.sid
    
    room = get_room_or_404(room_code)
    if not room:
        emit('error', {'message': 'Room not found or expired'})
        return
    
    # Check device limit
    active_devices = Device.query.filter_by(room_id=room.id).all()
    if len(active_devices) >= Config.MAX_DEVICES_PER_ROOM:
        emit('error', {'message': 'Room is full'})
        return
    
    # Update room activity
    room.update_activity()
    
    # Create device record
    device = Device(
        room_id=room.id,
        device_name=device_name,
        session_id=session_id
    )
    
    db.session.add(device)
    db.session.commit()
    
    # Join socket.io room
    join_room(room_code)
    
    # Store device_id in session for later use
    session['device_id'] = device.id
    session['room_code'] = room_code
    
    # Emit to all clients in room
    all_devices = Device.query.filter_by(room_id=room.id).all()
    devices_data = [d.to_dict() for d in all_devices]
    
    emit('devices_updated', {
        'devices': devices_data,
        'device_count': len(all_devices)
    }, room=room_code)
    
    emit('device_joined', {
        'device': device.to_dict(),
        'message': f'{device_name} joined the room'
    }, room=room_code)


@socketio.on('heartbeat')
def handle_heartbeat(data):
    """Handle device heartbeat to keep connection alive"""
    session_id = request.sid
    
    device = Device.query.filter_by(session_id=session_id).first()
    if device:
        device.update_heartbeat()
        room = device.room
        if room:
            room.update_activity()


@socketio.on('disconnect')
def handle_disconnect():
    """Handle device disconnection"""
    session_id = request.sid
    
    device = Device.query.filter_by(session_id=session_id).first()
    if device:
        room = device.room
        room_code = room.code
        
        # Delete device
        db.session.delete(device)
        db.session.commit()
        
        # Notify other devices
        remaining_devices = Device.query.filter_by(room_id=room.id).all()
        if remaining_devices:
            devices_data = [d.to_dict() for d in remaining_devices]
            socketio.emit('devices_updated', {
                'devices': devices_data,
                'device_count': len(remaining_devices)
            }, room=room_code, namespace='/')
            
            socketio.emit('device_left', {
                'device_name': device.device_name,
                'message': f'{device.device_name} left the room'
            }, room=room_code, namespace='/')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        'error': f'File exceeds {Config.MAX_UPLOAD_SIZE_MB}MB limit'
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('error.html', error='Page not found'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template('error.html', error='An error occurred'), 500


# ============================================================================
# APPLICATION INITIALIZATION
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_expired_rooms, daemon=True)
    cleanup_thread.start()
    
    # Run SocketIO server
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
