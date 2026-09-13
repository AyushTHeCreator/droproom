import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'droproom-dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///droproom.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Room settings
    ROOM_CODE_LENGTH = 6
    ROOM_EXPIRY_MINUTES = 30
    MAX_DEVICES_PER_ROOM = 10
    DEVICE_HEARTBEAT_TIMEOUT = 5  # minutes
    
    # File upload settings
    MAX_UPLOAD_SIZE_MB = 100
    MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',
        'mp4', 'avi', 'mov', 'mkv', 'webm',
        'zip', 'rar', '7z', 'tar', 'gz',
        'txt', 'md', 'csv', 'json', 'xml'
    }
    
    # Cleanup
    CLEANUP_CHECK_INTERVAL_SECONDS = 60
