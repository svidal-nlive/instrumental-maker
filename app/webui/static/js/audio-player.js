// Audio Player - Play instrumentals directly in the browser

class AudioPlayer {
    constructor() {
        this.audio = null;
        this.currentTrack = null;
        this.playlist = [];
    }

    async loadLibrary() {
        try {
            const response = await fetch('/api/files/library');
            const files = await response.json();
            this.playlist = files;
            this.renderLibrary();
        } catch (error) {
            console.error('Error loading library:', error);
        }
    }

    renderLibrary() {
        const container = document.getElementById('library-grid');
        if (!container) return;

        if (this.playlist.length === 0) {
            container.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <svg class="w-16 h-16 mx-auto text-gray-400 dark:text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                    </svg>
                    <p class="text-gray-500 dark:text-gray-400 font-medium">No instrumentals yet</p>
                    <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Process some files to build your library</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.playlist.map((track, index) => {
            const isPlaying = this.currentTrack?.path === track.path && this.audio && !this.audio.paused;
            const size = this.formatFileSize(track.size);
            const date = new Date(track.modified * 1000);
            
            return `
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-all group">
                    <!-- Album Art Placeholder -->
                    <div class="relative bg-gradient-to-br from-primary-500 to-accent-500 aspect-square flex items-center justify-center">
                        <svg class="w-16 h-16 text-white opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>
                        </svg>
                        <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all flex items-center justify-center">
                            <button 
                                onclick="audioPlayer.playTrack(${index})"
                                class="transform scale-0 group-hover:scale-100 transition-transform bg-white rounded-full p-4 shadow-lg hover:scale-110">
                                ${isPlaying ? `
                                    <svg class="w-6 h-6 text-gray-900" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"></path>
                                    </svg>
                                ` : `
                                    <svg class="w-6 h-6 text-gray-900" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M8 5v14l11-7z"></path>
                                    </svg>
                                `}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Track Info -->
                    <div class="p-4">
                        <h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate" title="${track.title}">
                            ${track.title}
                        </h3>
                        <p class="text-sm text-gray-500 dark:text-gray-400 truncate mt-0.5" title="${track.artist}">
                            ${track.artist}
                        </p>
                        <p class="text-xs text-gray-400 dark:text-gray-500 truncate" title="${track.album}">
                            ${track.album}
                        </p>
                        
                        <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                            <span class="text-xs text-gray-400 dark:text-gray-500">
                                ${size} • ${track.extension.toUpperCase().substring(1)}
                            </span>
                            <div class="flex gap-1">
                                <button 
                                    onclick="audioPlayer.downloadTrack('${track.path}')"
                                    class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                    title="Download">
                                    <svg class="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    playTrack(index) {
        const track = this.playlist[index];
        if (!track) return;

        // If same track and playing, pause it
        if (this.currentTrack?.path === track.path && this.audio && !this.audio.paused) {
            this.audio.pause();
            this.renderLibrary();
            this.hidePlayer();
            return;
        }

        // Create or update audio element
        if (!this.audio) {
            this.audio = new Audio();
            this.audio.addEventListener('ended', () => {
                this.playNext();
            });
            this.audio.addEventListener('timeupdate', () => {
                this.updatePlayerUI();
            });
            this.audio.addEventListener('loadedmetadata', () => {
                this.updatePlayerUI();
            });
        }

        this.currentTrack = track;
        this.audio.src = `/api/files/stream/${track.path}`;
        this.audio.play();
        this.showPlayer();
        this.renderLibrary(); // Update play button states
    }

    playNext() {
        const currentIndex = this.playlist.findIndex(t => t.path === this.currentTrack?.path);
        const nextIndex = (currentIndex + 1) % this.playlist.length;
        this.playTrack(nextIndex);
    }

    playPrevious() {
        const currentIndex = this.playlist.findIndex(t => t.path === this.currentTrack?.path);
        const prevIndex = (currentIndex - 1 + this.playlist.length) % this.playlist.length;
        this.playTrack(prevIndex);
    }

    togglePlayPause() {
        if (!this.audio) return;
        
        if (this.audio.paused) {
            this.audio.play();
        } else {
            this.audio.pause();
        }
        this.updatePlayerUI();
    }

    seek(percent) {
        if (!this.audio || !this.audio.duration) return;
        this.audio.currentTime = (percent / 100) * this.audio.duration;
    }

    setVolume(percent) {
        if (!this.audio) return;
        this.audio.volume = percent / 100;
    }

    showPlayer() {
        const player = document.getElementById('audio-player');
        if (player) {
            player.classList.remove('hidden');
            this.updatePlayerUI();
        }
    }

    hidePlayer() {
        const player = document.getElementById('audio-player');
        if (player) {
            player.classList.add('hidden');
        }
    }

    updatePlayerUI() {
        if (!this.audio || !this.currentTrack) return;

        const title = document.getElementById('player-title');
        const artist = document.getElementById('player-artist');
        const currentTime = document.getElementById('player-current-time');
        const duration = document.getElementById('player-duration');
        const progress = document.getElementById('player-progress');
        const playBtn = document.getElementById('player-play-btn');

        if (title) title.textContent = this.currentTrack.title;
        if (artist) artist.textContent = `${this.currentTrack.artist} - ${this.currentTrack.album}`;
        
        if (currentTime) currentTime.textContent = this.formatTime(this.audio.currentTime);
        if (duration) duration.textContent = this.formatTime(this.audio.duration || 0);
        
        if (progress) {
            const percent = (this.audio.currentTime / this.audio.duration) * 100 || 0;
            progress.style.width = `${percent}%`;
        }

        if (playBtn) {
            playBtn.innerHTML = this.audio.paused ? `
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"></path>
                </svg>
            ` : `
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"></path>
                </svg>
            `;
        }
    }

    downloadTrack(path) {
        window.location.href = `/api/files/download/${path}`;
    }

    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
}

// Initialize on page load
let audioPlayer;
document.addEventListener('DOMContentLoaded', () => {
    audioPlayer = new AudioPlayer();
});
