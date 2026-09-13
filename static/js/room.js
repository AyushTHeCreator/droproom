// Initialize Socket.IO connection
const socket = io();
let currentRoomCode = '';
let currentDeviceId = '';
let currentSessionId = '';
let isInitialized = false;

function initializeRoom(roomCode) {
    currentRoomCode = roomCode;
    
    // Generate unique session ID for this browser
    currentSessionId = generateSessionId();
    
    // Retrieve or ask for device name
    let deviceName = localStorage.getItem(`droproom_device_name_${roomCode}`);
    if (!deviceName) {
        deviceName = prompt('What should we call this device?', 'My Device');
        if (!deviceName) deviceName = 'Unknown Device';
        localStorage.setItem(`droproom_device_name_${roomCode}`, deviceName);
    }
    
    document.getElementById('device-name').value = deviceName;
    
    // Join the room via Socket.IO
    socket.emit('join_room', {
        room_code: roomCode,
        device_name: deviceName
    });
    
    // Setup drag and drop
    setupDragAndDrop();
    
    // Load existing files
    loadFiles();
    loadDevices();
    
    // Setup heartbeat
    setInterval(() => {
        socket.emit('heartbeat', { room_code: roomCode });
    }, 30000); // Every 30 seconds
    
    isInitialized = true;
}

function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

// Socket.IO Event Handlers
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('error', (data) => {
    showNotification(data.message || 'An error occurred', 'error');
});

socket.on('devices_updated', (data) => {
    console.log('Devices updated:', data);
    renderDevices(data.devices);
    document.getElementById('device-count').textContent = 
        `🟢 ${data.device_count} device${data.device_count !== 1 ? 's' : ''} connected`;
});

socket.on('device_joined', (data) => {
    showNotification(`✓ ${data.message}`, 'success');
});

socket.on('device_left', (data) => {
    showNotification(`✗ ${data.message}`, 'error');
});

socket.on('file_uploaded', (data) => {
    console.log('File uploaded:', data);
    loadFiles();
    showNotification(`✓ ${data.original_filename} uploaded`, 'success');
});

socket.on('file_deleted', (data) => {
    console.log('File deleted:', data);
    loadFiles();
});

socket.on('room_expired', () => {
    showNotification('This room has expired.', 'error');
    setTimeout(() => {
        window.location.href = '/';
    }, 2000);
});

// Load and render files
function loadFiles() {
    fetch(`/room/${currentRoomCode}/files`)
        .then(res => res.json())
        .then(files => {
            renderFiles(files);
        })
        .catch(err => console.error('Error loading files:', err));
}

function renderFiles(files) {
    const container = document.getElementById('files-list');
    
    if (!files || files.length === 0) {
        container.innerHTML = '<p class="empty-message">No files yet. Upload one to get started!</p>';
        return;
    }
    
    container.innerHTML = files.map(file => `
        <div class="file-item">
            <div style="display: flex; align-items: flex-start; flex: 1;">
                <span class="file-icon">${getFileIcon(file.mime_type)}</span>
                <div class="file-info">
                    <p class="file-name">${escapeHtml(file.original_filename)}</p>
                    <div class="file-meta">
                        <span>${formatFileSize(file.file_size)}</span>
                        <span>Uploaded by ${escapeHtml(file.uploaded_by)}</span>
                        <span>${formatTime(file.uploaded_at)}</span>
                    </div>
                </div>
            </div>
            <div class="file-actions">
                <a href="/room/${currentRoomCode}/download/${file.id}" class="btn-download" download>
                    Download
                </a>
                <button class="btn-delete" onclick="deleteFile('${file.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function getFileIcon(mimeType) {
    if (mimeType.startsWith('image')) return '🖼️';
    if (mimeType.startsWith('video')) return '🎬';
    if (mimeType.startsWith('audio')) return '🎵';
    if (mimeType.includes('pdf')) return '📕';
    if (mimeType.includes('word') || mimeType.includes('document')) return '📄';
    if (mimeType.includes('sheet') || mimeType.includes('excel')) return '📊';
    if (mimeType.includes('presentation') || mimeType.includes('powerpoint')) return '📑';
    if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('compress')) return '📦';
    return '📄';
}

// Load and render devices
function loadDevices() {
    fetch(`/room/${currentRoomCode}/devices`)
        .then(res => res.json())
        .then(devices => {
            if (devices.length > 0 && !currentDeviceId) {
                // Store the ID of the first device that we see (should be us)
                currentDeviceId = devices[0].id;
            }
        })
        .catch(err => console.error('Error loading devices:', err));
}

function renderDevices(devices) {
    const container = document.getElementById('devices-list');
    container.innerHTML = devices.map(device => `
        <div class="device-item">
            <span class="device-status ${device.is_active ? '' : 'inactive'}"></span>
            <span class="device-name">${escapeHtml(device.device_name)}</span>
        </div>
    `).join('');
}

// File upload handling
function setupDragAndDrop() {
    const uploadArea = document.getElementById('upload-area');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('dragover');
        }, false);
    });
    
    uploadArea.addEventListener('drop', handleDrop, false);
    uploadArea.addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
}

function handleFileSelect(event) {
    handleFiles(event.target.files);
}

function handleFiles(files) {
    const maxSize = window.maxUploadBytes || (100 * 1024 * 1024);
    
    for (let file of files) {
        if (file.size > maxSize) {
            showNotification(`File "${file.name}" is too large`, 'error');
            continue;
        }
        
        uploadFile(file);
    }
    
    // Reset file input
    document.getElementById('file-input').value = '';
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('device_id', currentDeviceId);
    
    // Show progress container
    const progressContainer = document.getElementById('upload-progress-container');
    progressContainer.style.display = 'block';
    
    // Use XMLHttpRequest for progress tracking
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            document.getElementById('upload-progress').innerHTML = `
                <div class="progress-bar" style="width: ${percentComplete}%"></div>
                <p class="progress-text">${file.name} - ${Math.round(percentComplete)}%</p>
            `;
        }
    });
    
    xhr.addEventListener('load', () => {
        if (xhr.status === 201) {
            showNotification(`✓ ${file.name} uploaded successfully`, 'success');
            progressContainer.style.display = 'none';
            loadFiles();
        } else {
            const response = JSON.parse(xhr.responseText);
            showNotification(`Error: ${response.error || 'Upload failed'}`, 'error');
            progressContainer.style.display = 'none';
        }
    });
    
    xhr.addEventListener('error', () => {
        showNotification('Upload failed. Check your connection.', 'error');
        progressContainer.style.display = 'none';
    });
    
    xhr.open('POST', `/room/${currentRoomCode}/upload`);
    xhr.send(formData);
}

function deleteFile(fileId) {
    if (!confirm('Delete this file?')) return;
    
    fetch(`/room/${currentRoomCode}/file/${fileId}`, {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        showNotification('✓ File deleted', 'success');
        loadFiles();
    })
    .catch(err => {
        showNotification('Error deleting file', 'error');
    });
}

function changeDeviceName() {
    const newName = document.getElementById('device-name').value.trim();
    if (!newName) {
        showNotification('Device name cannot be empty', 'error');
        return;
    }
    
    localStorage.setItem(`droproom_device_name_${currentRoomCode}`, newName);
    showNotification('Device name updated (will show on next join)', 'success');
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
}

function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 4000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
