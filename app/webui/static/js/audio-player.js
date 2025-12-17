/**
 * Enhanced Audio Player with minimized bar and expandable full view
 */
class AudioPlayer {
    constructor() {
        this.audio = new Audio();
        this.currentTrack = null;
        this.currentIndex = -1;
        this.tracks = [];
        this.isExpanded = false;
        this.isPlaying = false;
        
        this.initPlayer();
        this.bindEvents();
        this.loadLibrary();
    }
    
    initPlayer() {
        // Create minimized player bar (fixed at bottom)
        this.playerBar = document.createElement('div');
        this.playerBar.id = 'player-bar';
        this.playerBar.className = 'player-bar hidden';
        this.playerBar.innerHTML = `
            <div class="player-bar-content">
                <div class="player-bar-track">
                    <div class="player-bar-info">
                        <span class="player-bar-title">No track selected</span>
                        <span class="player-bar-artist"></span>
                    </div>
                </div>
                <div class="player-bar-controls">
                    <button class="player-btn" id="btn-prev" title="Previous">
                        <i class="fas fa-step-backward"></i>
                    </button>
                    <button class="player-btn player-btn-main" id="btn-play" title="Play/Pause">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="player-btn" id="btn-next" title="Next">
                        <i class="fas fa-step-forward"></i>
                    </button>
                </div>
                <div class="player-bar-progress">
                    <span class="player-time" id="current-time">0:00</span>
                    <input type="range" class="progress-slider" id="progress-slider" min="0" max="100" value="0">
                    <span class="player-time" id="duration">0:00</span>
                </div>
                <div class="player-bar-volume">
                    <i class="fas fa-volume-up"></i>
                    <input type="range" class="volume-slider" id="volume-slider" min="0" max="100" value="100">
                </div>
                <button class="player-btn" id="btn-expand" title="Expand">
                    <i class="fas fa-chevron-up"></i>
                </button>
            </div>
        `;
        document.body.appendChild(this.playerBar);
        
        // Create expanded player overlay
        this.playerExpanded = document.createElement('div');
        this.playerExpanded.id = 'player-expanded';
        this.playerExpanded.className = 'player-expanded hidden';
        this.playerExpanded.innerHTML = `
            <div class="player-expanded-content">
                <button class="player-btn player-close-btn" id="btn-collapse" title="Minimize">
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="player-expanded-artwork">
                    <i class="fas fa-music"></i>
                </div>
                <div class="player-expanded-info">
                    <h2 class="player-expanded-title">No track selected</h2>
                    <p class="player-expanded-artist"></p>
                    <p class="player-expanded-album"></p>
                </div>
                <div class="player-expanded-progress">
                    <input type="range" class="progress-slider-expanded" id="progress-slider-expanded" min="0" max="100" value="0">
                    <div class="player-expanded-times">
                        <span id="current-time-expanded">0:00</span>
                        <span id="duration-expanded">0:00</span>
                    </div>
                </div>
                <div class="player-expanded-controls">
                    <button class="player-btn" id="btn-prev-expanded" title="Previous">
                        <i class="fas fa-step-backward"></i>
                    </button>
                    <button class="player-btn player-btn-main-expanded" id="btn-play-expanded" title="Play/Pause">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="player-btn" id="btn-next-expanded" title="Next">
                        <i class="fas fa-step-forward"></i>
                    </button>
                </div>
                <div class="player-expanded-volume">
                    <i class="fas fa-volume-up" id="volume-icon-expanded"></i>
                    <input type="range" class="volume-slider-expanded" id="volume-slider-expanded" min="0" max="100" value="100">
                </div>
            </div>
        `;
        document.body.appendChild(this.playerExpanded);
        
        // Cache DOM elements AFTER appending to body
        this.elements = {
            // Bar elements - use querySelector on playerBar for reliability
            barTitle: this.playerBar.querySelector('.player-bar-title'),
            barArtist: this.playerBar.querySelector('.player-bar-artist'),
            btnPlay: this.playerBar.querySelector('#btn-play'),
            btnPrev: this.playerBar.querySelector('#btn-prev'),
            btnNext: this.playerBar.querySelector('#btn-next'),
            btnExpand: this.playerBar.querySelector('#btn-expand'),
            progressSlider: this.playerBar.querySelector('#progress-slider'),
            volumeSlider: this.playerBar.querySelector('#volume-slider'),
            currentTime: this.playerBar.querySelector('#current-time'),
            duration: this.playerBar.querySelector('#duration'),
            // Expanded elements - use querySelector on playerExpanded
            expandedTitle: this.playerExpanded.querySelector('.player-expanded-title'),
            expandedArtist: this.playerExpanded.querySelector('.player-expanded-artist'),
            expandedAlbum: this.playerExpanded.querySelector('.player-expanded-album'),
            btnPlayExpanded: this.playerExpanded.querySelector('#btn-play-expanded'),
            btnPrevExpanded: this.playerExpanded.querySelector('#btn-prev-expanded'),
            btnNextExpanded: this.playerExpanded.querySelector('#btn-next-expanded'),
            btnCollapse: this.playerExpanded.querySelector('#btn-collapse'),
            progressSliderExpanded: this.playerExpanded.querySelector('#progress-slider-expanded'),
            volumeSliderExpanded: this.playerExpanded.querySelector('#volume-slider-expanded'),
            currentTimeExpanded: this.playerExpanded.querySelector('#current-time-expanded'),
            durationExpanded: this.playerExpanded.querySelector('#duration-expanded'),
        };
        
        // Debug: verify elements are found
        console.log('Audio Player elements initialized:', {
            btnPlay: !!this.elements.btnPlay,
            btnExpand: !!this.elements.btnExpand,
            progressSlider: !!this.elements.progressSlider,
            btnCollapse: !!this.elements.btnCollapse
        });
        
        // Set initial volume
        this.audio.volume = 1.0;
    }
    
    bindEvents() {
        // Audio events
        this.audio.addEventListener('timeupdate', () => this.updateProgress());
        this.audio.addEventListener('loadedmetadata', () => this.updateDuration());
        this.audio.addEventListener('ended', () => this.playNext());
        this.audio.addEventListener('play', () => this.onPlay());
        this.audio.addEventListener('pause', () => this.onPause());
        this.audio.addEventListener('error', (e) => this.onError(e));
        
        // Bar controls - with null checks
        if (this.elements.btnPlay) this.elements.btnPlay.addEventListener('click', () => this.togglePlay());
        if (this.elements.btnPrev) this.elements.btnPrev.addEventListener('click', () => this.playPrev());
        if (this.elements.btnNext) this.elements.btnNext.addEventListener('click', () => this.playNext());
        if (this.elements.btnExpand) this.elements.btnExpand.addEventListener('click', () => this.expand());
        if (this.elements.progressSlider) this.elements.progressSlider.addEventListener('input', (e) => this.seek(e.target.value));
        if (this.elements.volumeSlider) this.elements.volumeSlider.addEventListener('input', (e) => this.setVolume(e.target.value));
        
        // Expanded controls - with null checks
        if (this.elements.btnPlayExpanded) this.elements.btnPlayExpanded.addEventListener('click', () => this.togglePlay());
        if (this.elements.btnPrevExpanded) this.elements.btnPrevExpanded.addEventListener('click', () => this.playPrev());
        if (this.elements.btnNextExpanded) this.elements.btnNextExpanded.addEventListener('click', () => this.playNext());
        if (this.elements.btnCollapse) this.elements.btnCollapse.addEventListener('click', () => this.collapse());
        if (this.elements.progressSliderExpanded) this.elements.progressSliderExpanded.addEventListener('input', (e) => this.seek(e.target.value));
        if (this.elements.volumeSliderExpanded) this.elements.volumeSliderExpanded.addEventListener('input', (e) => this.setVolume(e.target.value));
        
        // Click outside expanded to close
        this.playerExpanded.addEventListener('click', (e) => {
            if (e.target === this.playerExpanded) {
                this.collapse();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            switch (e.code) {
                case 'Space':
                    e.preventDefault();
                    this.togglePlay();
                    break;
                case 'ArrowLeft':
                    if (e.shiftKey) this.playPrev();
                    else this.seekRelative(-10);
                    break;
                case 'ArrowRight':
                    if (e.shiftKey) this.playNext();
                    else this.seekRelative(10);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.adjustVolume(0.1);
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    this.adjustVolume(-0.1);
                    break;
                case 'Escape':
                    if (this.isExpanded) this.collapse();
                    break;
            }
        });
    }
    
    async loadLibrary() {
        const libraryContainer = document.getElementById('library-grid');
        if (!libraryContainer) {
            console.log('Library container not found');
            return;
        }
        
        try {
            const response = await fetch('/api/files/library');
            if (!response.ok) throw new Error('Failed to load library');
            
            const data = await response.json();
            // API returns array directly, not { files: [...] }
            this.tracks = Array.isArray(data) ? data : (data.files || []);
            console.log(`Loaded ${this.tracks.length} tracks`);
            this.renderLibrary(libraryContainer);
        } catch (error) {
            console.error('Error loading library:', error);
            libraryContainer.innerHTML = `
                <div class="error-message col-span-full">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Failed to load library: ${error.message}</p>
                </div>
            `;
        }
    }
    
    renderLibrary(container) {
        if (this.tracks.length === 0) {
            container.innerHTML = `
                <div class="empty-library col-span-full">
                    <i class="fas fa-music"></i>
                    <p>No tracks in library</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.tracks.map((track, index) => `
            <div class="library-card" data-index="${index}">
                <div class="library-card-artwork">
                    <i class="fas fa-music"></i>
                    <button class="library-card-play" data-index="${index}" title="Play">
                        <i class="fas fa-play"></i>
                    </button>
                </div>
                <div class="library-card-info">
                    <div class="library-card-title" title="${this.escapeHtml(track.name)}">${this.escapeHtml(track.name)}</div>
                    <div class="library-card-details">
                        ${track.size ? this.formatSize(track.size) : ''} 
                        ${track.modified ? '• ' + this.formatDate(track.modified) : ''}
                    </div>
                </div>
                <div class="library-card-actions">
                    <a href="/api/files/download/${encodeURIComponent(track.path)}" 
                       class="library-card-btn" title="Download">
                        <i class="fas fa-download"></i>
                    </a>
                    <button class="library-card-btn library-card-delete" 
                            data-path="${this.escapeHtml(track.path)}" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
        
        // Bind play buttons
        container.querySelectorAll('.library-card-play').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(btn.dataset.index);
                console.log(`Play button clicked for track ${index}`);
                this.playTrack(index);
            });
        });
        
        // Bind delete buttons
        container.querySelectorAll('.library-card-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const path = btn.dataset.path;
                this.deleteTrack(path);
            });
        });
        
        // Bind card clicks (play on double-click)
        container.querySelectorAll('.library-card').forEach(card => {
            card.addEventListener('dblclick', () => {
                const index = parseInt(card.dataset.index);
                this.playTrack(index);
            });
        });
    }
    
    playTrack(index) {
        if (index < 0 || index >= this.tracks.length) {
            console.error('Invalid track index:', index);
            return;
        }
        
        const track = this.tracks[index];
        console.log(`Playing track: ${track.name} (${track.path})`);
        
        this.currentIndex = index;
        this.currentTrack = track;
        
        // Build stream URL
        const streamUrl = `/api/files/stream/${encodeURIComponent(track.path)}`;
        console.log(`Stream URL: ${streamUrl}`);
        
        // Set audio source and play
        this.audio.src = streamUrl;
        this.audio.load();
        
        const playPromise = this.audio.play();
        if (playPromise !== undefined) {
            playPromise
                .then(() => {
                    console.log('Playback started successfully');
                })
                .catch(error => {
                    console.error('Playback failed:', error);
                    this.showNotification(`Playback failed: ${error.message}`, 'error');
                });
        }
        
        // Update UI
        this.updateTrackInfo();
        this.showPlayerBar();
        this.highlightCurrentTrack();
    }
    
    updateTrackInfo() {
        if (!this.currentTrack) return;
        
        const title = this.currentTrack.name || 'Unknown';
        const artist = this.extractArtist(this.currentTrack.path);
        const album = this.extractAlbum(this.currentTrack.path);
        
        // Update bar
        this.elements.barTitle.textContent = title;
        this.elements.barArtist.textContent = artist;
        
        // Update expanded
        this.elements.expandedTitle.textContent = title;
        this.elements.expandedArtist.textContent = artist;
        this.elements.expandedAlbum.textContent = album;
    }
    
    extractArtist(path) {
        // Try to extract artist from path: artist/album/track.mp3
        const parts = path.split('/').filter(p => p);
        if (parts.length >= 2) {
            return parts[parts.length - 2];
        }
        return '';
    }
    
    extractAlbum(path) {
        // Try to extract album from path
        const parts = path.split('/').filter(p => p);
        if (parts.length >= 3) {
            return parts[parts.length - 2];
        }
        return '';
    }
    
    showPlayerBar() {
        this.playerBar.classList.remove('hidden');
        document.body.classList.add('has-player');
    }
    
    hidePlayerBar() {
        this.playerBar.classList.add('hidden');
        document.body.classList.remove('has-player');
    }
    
    highlightCurrentTrack() {
        // Remove highlight from all cards
        document.querySelectorAll('.library-card').forEach(card => {
            card.classList.remove('playing');
        });
        
        // Add highlight to current card
        const currentCard = document.querySelector(`.library-card[data-index="${this.currentIndex}"]`);
        if (currentCard) {
            currentCard.classList.add('playing');
        }
    }
    
    togglePlay() {
        if (this.audio.paused) {
            this.audio.play().catch(e => console.error('Play failed:', e));
        } else {
            this.audio.pause();
        }
    }
    
    onPlay() {
        this.isPlaying = true;
        this.updatePlayButton(true);
    }
    
    onPause() {
        this.isPlaying = false;
        this.updatePlayButton(false);
    }
    
    updatePlayButton(isPlaying) {
        const icon = isPlaying ? 'fa-pause' : 'fa-play';
        if (this.elements.btnPlay) this.elements.btnPlay.innerHTML = `<i class="fas ${icon}"></i>`;
        if (this.elements.btnPlayExpanded) this.elements.btnPlayExpanded.innerHTML = `<i class="fas ${icon}"></i>`;
    }
    
    onError(e) {
        console.error('Audio error:', this.audio.error);
        const errorMessages = {
            1: 'Playback aborted',
            2: 'Network error',
            3: 'Decoding error',
            4: 'Format not supported'
        };
        const message = errorMessages[this.audio.error?.code] || 'Unknown error';
        this.showNotification(`Audio error: ${message}`, 'error');
    }
    
    playNext() {
        if (this.tracks.length === 0) return;
        
        let nextIndex = this.currentIndex + 1;
        if (nextIndex >= this.tracks.length) {
            nextIndex = 0; // Loop to beginning
        }
        this.playTrack(nextIndex);
    }
    
    playPrev() {
        if (this.tracks.length === 0) return;
        
        // If more than 3 seconds in, restart current track
        if (this.audio.currentTime > 3) {
            this.audio.currentTime = 0;
            return;
        }
        
        let prevIndex = this.currentIndex - 1;
        if (prevIndex < 0) {
            prevIndex = this.tracks.length - 1; // Loop to end
        }
        this.playTrack(prevIndex);
    }
    
    updateProgress() {
        if (this.audio.duration && !isNaN(this.audio.duration)) {
            const percent = (this.audio.currentTime / this.audio.duration) * 100;
            if (this.elements.progressSlider) this.elements.progressSlider.value = percent;
            if (this.elements.progressSliderExpanded) this.elements.progressSliderExpanded.value = percent;
            
            const timeStr = this.formatTime(this.audio.currentTime);
            if (this.elements.currentTime) this.elements.currentTime.textContent = timeStr;
            if (this.elements.currentTimeExpanded) this.elements.currentTimeExpanded.textContent = timeStr;
        }
    }
    
    updateDuration() {
        if (this.audio.duration && !isNaN(this.audio.duration)) {
            const durationStr = this.formatTime(this.audio.duration);
            if (this.elements.duration) this.elements.duration.textContent = durationStr;
            if (this.elements.durationExpanded) this.elements.durationExpanded.textContent = durationStr;
        }
    }
    
    seek(percent) {
        if (this.audio.duration) {
            this.audio.currentTime = (percent / 100) * this.audio.duration;
        }
    }
    
    seekRelative(seconds) {
        this.audio.currentTime = Math.max(0, Math.min(this.audio.duration || 0, this.audio.currentTime + seconds));
    }
    
    setVolume(percent) {
        this.audio.volume = percent / 100;
        if (this.elements.volumeSlider) this.elements.volumeSlider.value = percent;
        if (this.elements.volumeSliderExpanded) this.elements.volumeSliderExpanded.value = percent;
    }
    
    adjustVolume(delta) {
        const newVolume = Math.max(0, Math.min(1, this.audio.volume + delta));
        this.setVolume(newVolume * 100);
    }
    
    expand() {
        this.isExpanded = true;
        this.playerExpanded.classList.remove('hidden');
        document.body.classList.add('player-expanded-open');
    }
    
    collapse() {
        this.isExpanded = false;
        this.playerExpanded.classList.add('hidden');
        document.body.classList.remove('player-expanded-open');
    }
    
    async deleteTrack(path) {
        if (!confirm(`Delete "${path.split('/').pop()}"?`)) return;
        
        try {
            const response = await fetch('/api/files/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to delete');
            }
            
            this.showNotification('Track deleted', 'success');
            
            // Reload library
            this.loadLibrary();
        } catch (error) {
            console.error('Delete failed:', error);
            this.showNotification(`Delete failed: ${error.message}`, 'error');
        }
    }
    
    showNotification(message, type = 'info') {
        // Create notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${this.escapeHtml(message)}</span>
        `;
        
        // Add to document
        let container = document.querySelector('.notification-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'notification-container';
            document.body.appendChild(container);
        }
        container.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    formatSize(bytes) {
        if (!bytes) return '';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return `${bytes.toFixed(1)} ${units[i]}`;
    }
    
    formatDate(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString();
    }
    
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize player when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Audio Player');
    window.audioPlayer = new AudioPlayer();
});
