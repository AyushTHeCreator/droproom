from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from config import Config
import uuid

db = SQLAlchemy()


class Room(db.Model):
    __tablename__ = 'room'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # Relationships
    devices = db.relationship('Device', backref='room', cascade='all, delete-orphan', lazy=True)
    files = db.relationship('File', backref='room', cascade='all, delete-orphan', lazy=True)
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def update_activity(self):
        self.last_activity = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(minutes=Config.ROOM_EXPIRY_MINUTES)
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'created_at': self.created_at.isoformat(),
            'device_count': len(self.devices)
        }


class Device(db.Model):
    __tablename__ = 'device'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('room.id'), nullable=False, index=True)
    device_name = db.Column(db.String(100), nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    files = db.relationship('File', backref='device', cascade='all, delete-orphan', lazy=True)
    
    def is_active(self):
        time_diff = datetime.utcnow() - self.last_seen
        return time_diff.total_seconds() < Config.DEVICE_HEARTBEAT_TIMEOUT * 60
    
    def update_heartbeat(self):
        self.last_seen = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_name': self.device_name,
            'session_id': self.session_id,
            'joined_at': self.joined_at.isoformat(),
            'is_active': self.is_active()
        }


class File(db.Model):
    __tablename__ = 'file'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('room.id'), nullable=False, index=True)
    device_id = db.Column(db.String(36), db.ForeignKey('device.id'), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self, include_uploader_name=True):
        result = {
            'id': self.id,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'uploaded_at': self.uploaded_at.isoformat()
        }
        if include_uploader_name:
            result['uploaded_by'] = self.device.device_name
        return result
