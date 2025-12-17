// Instrumental Maker Web UI - Main JavaScript

// ========================================
// TOAST NOTIFICATION SYSTEM
// ========================================
const Toast = {
    container: null,
    
    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.setAttribute('aria-live', 'polite');
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = 5000) {
        if (!this.container) this.init();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>',
            error: '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>',
            warning: '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>',
            info: '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
        };
        
        toast.innerHTML = `
            ${icons[type] || icons.info}
            <span class="flex-1 text-sm font-medium">${message}</span>
            <button onclick="this.parentElement.remove()" class="shrink-0 p-1 rounded-full hover:bg-white/20 transition-colors" aria-label="Dismiss">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        `;
        
        this.container.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'fadeOut 0.3s ease forwards';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
        
        return toast;
    },
    
    success(message, duration) { return this.show(message, 'success', duration); },
    error(message, duration) { return this.show(message, 'error', duration); },
    warning(message, duration) { return this.show(message, 'warning', duration); },
    info(message, duration) { return this.show(message, 'info', duration); }
};

// Make Toast globally available
window.Toast = Toast;

// ========================================
// MOBILE SIDEBAR TOGGLE
// ========================================
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const menuToggle = document.getElementById('menu-toggle');
    
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    
    // Update ARIA state
    const isOpen = sidebar.classList.contains('open');
    if (menuToggle) {
        menuToggle.setAttribute('aria-expanded', isOpen.toString());
    }
    
    // Prevent body scroll when sidebar is open
    document.body.style.overflow = isOpen ? 'hidden' : '';
}

// Close sidebar when clicking a nav link on mobile
function initMobileNav() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 768) {
                toggleSidebar();
            }
        });
    });
    
    // Close sidebar on resize to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768) {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    });
    
    // Close sidebar on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar.classList.contains('open')) {
                toggleSidebar();
            }
        }
    });
}

// Theme Management
function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;
    const lightIcon = document.getElementById('theme-icon-light');
    const darkIcon = document.getElementById('theme-icon-dark');
    const themeText = document.getElementById('theme-text');

    // Check for saved theme or default to system preference
    const savedTheme = localStorage.getItem('theme');
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && systemDark)) {
        html.classList.add('dark');
        darkIcon.classList.remove('hidden');
        themeText.textContent = 'Dark Mode';
    } else {
        html.classList.remove('dark');
        lightIcon.classList.remove('hidden');
        themeText.textContent = 'Light Mode';
    }

    themeToggle.addEventListener('click', () => {
        if (html.classList.contains('dark')) {
            html.classList.remove('dark');
            localStorage.setItem('theme', 'light');
            darkIcon.classList.add('hidden');
            lightIcon.classList.remove('hidden');
            themeText.textContent = 'Light Mode';
        } else {
            html.classList.add('dark');
            localStorage.setItem('theme', 'dark');
            lightIcon.classList.add('hidden');
            darkIcon.classList.remove('hidden');
            themeText.textContent = 'Dark Mode';
        }
    });
}

// Navigation
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const pages = document.querySelectorAll('.page-content');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const pageName = link.dataset.page;

            // Update active nav link
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            // Show selected page
            pages.forEach(page => page.classList.add('hidden'));
            document.getElementById(`page-${pageName}`).classList.remove('hidden');

            // Update header
            updatePageHeader(pageName);

            // Load page data
            loadPageData(pageName);
        });
    });
}

function updatePageHeader(pageName) {
    const titles = {
        dashboard: { title: 'Dashboard', subtitle: 'Overview of your instrumental processing pipeline' },
        queue: { title: 'Queue', subtitle: 'Files waiting to be processed' },
        library: { title: 'Library', subtitle: 'Your collection of instrumentals' },
        upload: { title: 'Upload', subtitle: 'Add new files to the processing queue' },
        logs: { title: 'Logs', subtitle: 'Real-time processing logs and events' },
        storage: { title: 'Storage', subtitle: 'Disk usage and cleanup management' },
        nas: { title: 'NAS Sync', subtitle: 'Monitor and control network storage synchronization' },
        youtube: { title: 'YouTube Download', subtitle: 'Download audio from YouTube and add to processing queue' }
    };

    const page = titles[pageName] || { title: 'Unknown', subtitle: '' };
    document.getElementById('page-title').textContent = page.title;
    document.getElementById('page-subtitle').textContent = page.subtitle;
}

// API Calls
async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`/api${endpoint}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API fetch error:', error);
        return null;
    }
}

// Dashboard Updates
async function updateDashboard() {
    const stats = await fetchAPI('/dashboard/stats');
    if (!stats) return;

    // Update stat cards
    document.getElementById('stat-queue').textContent = stats.queue.total_tracks;
    document.getElementById('stat-library').textContent = stats.library.total_instrumentals;
    document.getElementById('stat-processed').textContent = stats.recent.processed_24h;
    document.getElementById('stat-failed').textContent = stats.recent.failed_24h;

    // Update processor status
    updateProcessorStatus(stats.processor);

    // Load recent jobs
    loadRecentJobs();
}

async function loadRecentJobs() {
    const jobs = await fetchAPI('/dashboard/recent-jobs');
    if (!jobs) return;

    const container = document.getElementById('recent-jobs');
    
    if (jobs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
                <p class="empty-state-title">No recent jobs</p>
                <p class="empty-state-text">Upload some audio files to get started</p>
            </div>
        `;
        return;
    }

    container.innerHTML = jobs.slice(0, 10).map(job => `
        <div class="job-item ${job.status === 'completed' ? 'success' : 'error'} flex items-center justify-between p-3 md:p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-all gap-3">
            <div class="flex items-center space-x-3 md:space-x-4 flex-1 min-w-0">
                <div class="w-8 h-8 md:w-10 md:h-10 rounded-lg shrink-0 ${job.status === 'completed' ? 'bg-green-100 dark:bg-green-900' : 'bg-red-100 dark:bg-red-900'} flex items-center justify-center">
                    ${job.status === 'completed' 
                        ? '<svg class="w-4 h-4 md:w-5 md:h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
                        : '<svg class="w-4 h-4 md:w-5 md:h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
                    }
                </div>
                <div class="flex-1 min-w-0">
                    <p class="font-semibold text-sm md:text-base text-gray-900 dark:text-gray-100 truncate">${job.filename}</p>
                    <p class="text-xs md:text-sm text-gray-500 dark:text-gray-400 truncate">${job.artist} - ${job.album}</p>
                </div>
            </div>
            <div class="text-right shrink-0">
                <span class="badge ${job.status === 'completed' ? 'badge-success' : 'badge-error'}">${job.status}</span>
                <p class="text-xs text-gray-400 mt-1">${formatTimestamp(job.timestamp)}</p>
            </div>
        </div>
    `).join('');
}

function updateProcessorStatus(processor) {
    const statusEl = document.getElementById('processor-status');
    
    if (processor.running) {
        statusEl.innerHTML = `
            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span class="text-xs md:text-sm font-medium hidden sm:inline">Processing Active</span>
        `;
        statusEl.className = 'flex items-center space-x-2 px-2 md:px-4 py-1.5 md:py-2 rounded-full bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300';
    } else {
        statusEl.innerHTML = `
            <div class="w-2 h-2 rounded-full bg-gray-400"></div>
            <span class="text-xs md:text-sm font-medium hidden sm:inline">Idle</span>
        `;
        statusEl.className = 'flex items-center space-x-2 px-2 md:px-4 py-1.5 md:py-2 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300';
    }
}

// Load page-specific data
async function loadPageData(pageName) {
    switch (pageName) {
        case 'dashboard':
            updateDashboard();
            break;
        case 'queue':
            loadQueue();
            break;
        case 'library':
            // Audio player will handle library loading
            if (window.audioPlayer) {
                window.audioPlayer.loadLibrary();
            }
            break;
        case 'logs':
            loadLogs();
            break;
        case 'storage':
            loadStorageStats();
            break;
        case 'nas':
            loadNasStats();
            break;
    }
}

async function loadQueue() {
    const data = await fetchAPI('/files/incoming');
    const container = document.getElementById('queue-content');
    
    if (!data || !data.children || data.children.length === 0) {
        container.innerHTML = '<p class="text-gray-400">Queue is empty</p>';
        return;
    }

    container.innerHTML = renderFileTree(data.children);
}

// Note: loadLibrary removed - now handled by audio-player.js

function renderFileTree(items) {
    return `
        <div class="space-y-2">
            ${items.map(item => {
                if (item.type === 'directory') {
                    return `
                        <div class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                            <div class="flex items-center space-x-3 mb-2">
                                <svg class="w-5 h-5 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                                </svg>
                                <span class="font-medium">${item.name}</span>
                            </div>
                            ${item.children && item.children.length > 0 ? `
                                <div class="ml-8 space-y-1">
                                    ${item.children.map(child => {
                                        if (child.type === 'file') {
                                            return `
                                                <div class="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-700 rounded hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                                                    <div class="flex items-center space-x-2">
                                                        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>
                                                        </svg>
                                                        <span class="text-sm">${child.name}</span>
                                                    </div>
                                                    <span class="text-xs text-gray-400">${formatFileSize(child.size)}</span>
                                                </div>
                                            `;
                                        }
                                        return '';
                                    }).join('')}
                                </div>
                            ` : ''}
                        </div>
                    `;
                }
                return '';
            }).join('')}
        </div>
    `;
}

async function loadLogs() {
    const logs = await fetchAPI('/logs/recent?limit=100');
    const container = document.getElementById('logs-content');
    
    if (!logs || logs.length === 0) {
        container.innerHTML = '<p class="text-gray-400">No logs available</p>';
        return;
    }

    container.innerHTML = logs.map(log => {
        const eventClass = log.event === 'processed' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
        return `
            <div class="py-1 border-b border-gray-200 dark:border-gray-700">
                <span class="text-gray-400">${formatTimestamp(log.timestamp)}</span>
                <span class="${eventClass} font-bold ml-2">${log.event}</span>
                <span class="text-gray-300 dark:text-gray-600 ml-2">${log.title || 'Unknown'}</span>
            </div>
        `;
    }).join('');

    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Clear Processing History
async function clearProcessingHistory() {
    const confirmed = confirm('Are you sure you want to clear all processing history? This action cannot be undone.');
    if (!confirmed) return;

    try {
        const response = await fetch('/api/processing/clear-history', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            Toast.success(result.message || 'Processing history cleared successfully');
            // Reload recent jobs if available
            if (typeof loadRecentJobs === 'function') {
                loadRecentJobs();
            }
        } else {
            Toast.error('Failed to clear processing history');
        }
    } catch (error) {
        console.error('Error clearing history:', error);
        Toast.error('Error clearing processing history: ' + error.message);
    }
}

// Clear Processing Logs
async function clearProcessingLogs() {
    const confirmed = confirm('Are you sure you want to clear all processing logs? This action cannot be undone.');
    if (!confirmed) return;

    try {
        const response = await fetch('/api/logs/clear', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            Toast.success(result.message || 'Processing logs cleared successfully');
            // Reload logs if available
            if (typeof loadLogs === 'function') {
                loadLogs();
            }
        } else {
            Toast.error('Failed to clear processing logs');
        }
    } catch (error) {
        console.error('Error clearing logs:', error);
        Toast.error('Error clearing processing logs: ' + error.message);
    }
}

// Storage Management Functions
async function loadStorageStats() {
    try {
        const stats = await fetchAPI('/storage/stats');
        if (!stats) {
            document.getElementById('disk-usage-container').innerHTML = '<p class="text-red-500">Failed to load storage stats</p>';
            return;
        }

        // Display disk usage
        const diskHtml = `
            <div class="space-y-3">
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-medium">Disk Usage</span>
                        <span class="text-sm font-bold text-primary-600 dark:text-primary-400">${stats.disk.percent_used}%</span>
                    </div>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                        <div class="bg-gradient-to-r from-primary-500 to-accent-500 h-full transition-all" style="width: ${stats.disk.percent_used}%"></div>
                    </div>
                    <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        ${stats.disk.used_human} / ${stats.disk.total_human}
                    </div>
                </div>
                <div class="text-xs text-gray-600 dark:text-gray-300 space-y-1 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <p><strong>Available:</strong> ${stats.disk.available_human}</p>
                    <p><strong>Pipeline Usage:</strong> ${stats.pipeline.total_human} (${stats.pipeline.percent_of_disk}%)</p>
                </div>
            </div>
        `;
        document.getElementById('disk-usage-container').innerHTML = diskHtml;

        // Display directory breakdown
        const dirs = stats.directories;
        const dirHtml = `
            <div class="space-y-2">
                ${[
                    { name: 'Incoming Queue', key: 'incoming', color: 'blue' },
                    { name: 'Output Library', key: 'output', color: 'green' },
                    { name: 'Working (Processing)', key: 'working', color: 'yellow' },
                    { name: 'Archive', key: 'archive', color: 'purple' },
                    { name: 'Quarantine', key: 'quarantine', color: 'red' }
                ].map(dir => {
                    const data = dirs[dir.key];
                    const colorClass = {
                        'blue': 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300',
                        'green': 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300',
                        'yellow': 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300',
                        'purple': 'bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300',
                        'red': 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300'
                    }[dir.color];
                    return `
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                            <div class="flex-1">
                                <p class="font-medium text-sm">${dir.name}</p>
                                <p class="text-xs text-gray-500 dark:text-gray-400">${data.file_count} files</p>
                            </div>
                            <div class="text-right">
                                <p class="font-semibold text-sm">${data.size_human}</p>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        document.getElementById('directory-breakdown').innerHTML = dirHtml;
    } catch (error) {
        console.error('Error loading storage stats:', error);
        document.getElementById('disk-usage-container').innerHTML = '<p class="text-red-500">Error loading storage stats</p>';
    }
}

async function cleanupWorkingDirectory() {
    const confirmed = confirm('Are you sure you want to clean up the working directory? This will remove all temporary processing files.');
    if (!confirmed) return;

    try {
        const response = await fetch('/api/storage/cleanup', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            Toast.success(`${result.message} - Cleaned: ${result.cleaned_human}`);
            loadStorageStats(); // Refresh stats
        } else {
            Toast.error('Failed to cleanup working directory');
        }
    } catch (error) {
        console.error('Error cleaning up working directory:', error);
        Toast.error('Error cleaning up: ' + error.message);
    }
}

async function emptyQuarantine() {
    const confirmed = confirm('Are you sure you want to empty the quarantine directory? This will permanently delete all quarantined files.');
    if (!confirmed) return;

    try {
        const response = await fetch('/api/storage/empty-quarantine', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            Toast.success(`${result.message} - Removed: ${result.removed_human}`);
            loadStorageStats(); // Refresh stats
        } else {
            Toast.error('Failed to empty quarantine');
        }
    } catch (error) {
        console.error('Error emptying quarantine:', error);
        Toast.error('Error emptying quarantine: ' + error.message);
    }
}

// Upload handling
function initUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    if (!dropZone || !fileInput) return;
    
    // Click to open file dialog
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Keyboard accessibility
    dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        // Only remove if we're leaving the drop zone entirely
        if (!dropZone.contains(e.relatedTarget)) {
            dropZone.classList.remove('drag-over');
        }
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
        // Reset input so same file can be selected again
        fileInput.value = '';
    });
}

async function handleFiles(files) {
    if (files.length === 0) return;
    
    const progressContainer = document.getElementById('upload-progress-container');
    const progressList = document.getElementById('upload-progress-list');
    
    if (progressContainer && progressList) {
        progressContainer.classList.remove('hidden');
    }
    
    Toast.info(`Uploading ${files.length} file${files.length > 1 ? 's' : ''}...`);
    
    let successCount = 0;
    let errorCount = 0;
    
    for (const file of files) {
        const result = await uploadFile(file);
        if (result) {
            successCount++;
        } else {
            errorCount++;
        }
    }
    
    // Hide progress after a delay
    if (progressContainer) {
        setTimeout(() => {
            progressContainer.classList.add('hidden');
            if (progressList) progressList.innerHTML = '';
        }, 3000);
    }
    
    // Show summary
    if (successCount > 0) {
        Toast.success(`Successfully uploaded ${successCount} file${successCount > 1 ? 's' : ''}`);
    }
    if (errorCount > 0) {
        Toast.error(`Failed to upload ${errorCount} file${errorCount > 1 ? 's' : ''}`);
    }
    
    // Refresh dashboard
    updateDashboard();
}

async function uploadFile(file) {
    const progressList = document.getElementById('upload-progress-list');
    
    // Create progress item
    const progressItem = document.createElement('div');
    progressItem.className = 'flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg';
    progressItem.innerHTML = `
        <div class="shrink-0">
            <svg class="w-5 h-5 text-primary-600 dark:text-primary-400 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        </div>
        <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">${file.name}</p>
            <div class="mt-1">
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: 0%"></div>
                </div>
            </div>
        </div>
        <span class="text-xs text-gray-500 dark:text-gray-400 shrink-0">${formatFileSize(file.size)}</span>
    `;
    
    if (progressList) {
        progressList.appendChild(progressItem);
    }
    
    const progressFill = progressItem.querySelector('.progress-bar-fill');
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && progressFill) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    progressFill.style.width = `${percent}%`;
                }
            });
            
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(xhr.response);
                } else {
                    reject(new Error(`Upload failed: ${xhr.status}`));
                }
            });
            
            xhr.addEventListener('error', () => reject(new Error('Network error')));
            xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));
            
            xhr.open('POST', '/api/files/upload');
            xhr.send(formData);
        });

        // Success - update progress item
        progressItem.innerHTML = `
            <div class="shrink-0">
                <svg class="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
            </div>
            <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">${file.name}</p>
                <p class="text-xs text-green-600 dark:text-green-400">Uploaded successfully</p>
            </div>
        `;
        
        console.log('File uploaded:', file.name);
        return true;
    } catch (error) {
        // Error - update progress item
        progressItem.innerHTML = `
            <div class="shrink-0">
                <svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </div>
            <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">${file.name}</p>
                <p class="text-xs text-red-600 dark:text-red-400">Upload failed</p>
            </div>
        `;
        
        console.error('Upload error:', error);
        return false;
    }
}

// Utility functions
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// NAS Sync Functions
async function loadNasStats() {
    try {
        // Load status
        const status = await fetchAPI('/nas/status');
        if (status) {
            const statusHtml = `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-gradient-to-br from-primary-50 to-accent-50 dark:from-primary-900 dark:to-accent-900 rounded-lg p-4">
                        <p class="text-sm text-gray-600 dark:text-gray-300 mb-1">Last Sync</p>
                        <p class="text-2xl font-bold text-primary-600 dark:text-primary-300">${status.last_sync_time || 'Never'}</p>
                    </div>
                    <div class="bg-gradient-to-br from-primary-50 to-accent-50 dark:from-primary-900 dark:to-accent-900 rounded-lg p-4">
                        <p class="text-sm text-gray-600 dark:text-gray-300 mb-1">Status</p>
                        <div class="flex items-center gap-2">
                            <div class="w-3 h-3 rounded-full ${status.last_sync_success ? 'bg-green-500' : 'bg-red-500'}"></div>
                            <p class="text-lg font-semibold">${status.last_sync_success ? 'Success' : 'Failed'}</p>
                        </div>
                    </div>
                    <div class="bg-gradient-to-br from-primary-50 to-accent-50 dark:from-primary-900 dark:to-accent-900 rounded-lg p-4">
                        <p class="text-sm text-gray-600 dark:text-gray-300 mb-1">Files Synced</p>
                        <p class="text-2xl font-bold text-primary-600 dark:text-primary-300">${status.files_synced_last || 0}</p>
                    </div>
                    <div class="bg-gradient-to-br from-primary-50 to-accent-50 dark:from-primary-900 dark:to-accent-900 rounded-lg p-4">
                        <p class="text-sm text-gray-600 dark:text-gray-300 mb-1">Data Synced</p>
                        <p class="text-2xl font-bold text-primary-600 dark:text-primary-300">${status.bytes_synced_last_human || '0 B'}</p>
                    </div>
                </div>
            `;
            document.getElementById('nas-status-container').innerHTML = statusHtml;
        }

        // Load configuration
        const config = await fetchAPI('/nas/config');
        if (config) {
            const configHtml = `
                <div class="space-y-3">
                    ${Object.entries(config).map(([key, value]) => `
                        <div class="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                            <p class="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">${key.replace(/_/g, ' ')}</p>
                            <p class="text-sm font-medium text-gray-900 dark:text-gray-100 mt-1">${value}</p>
                        </div>
                    `).join('')}
                </div>
            `;
            document.getElementById('nas-config-container').innerHTML = configHtml;
        }

        // Load history
        const history = await fetchAPI('/nas/history');
        if (history && history.syncs) {
            const historyHtml = history.syncs.slice(0, 20).map(sync => `
                <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-3 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full ${sync.success ? 'bg-green-500' : 'bg-red-500'}"></div>
                            <span class="font-medium text-sm">${new Date(sync.timestamp * 1000).toLocaleString()}</span>
                        </div>
                        <span class="text-xs font-semibold px-2 py-1 rounded-full ${sync.success ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300' : 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300'}">
                            ${sync.success ? 'Success' : 'Failed'}
                        </span>
                    </div>
                    <div class="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                        <p><strong>Files:</strong> ${sync.files_synced} | <strong>Data:</strong> ${sync.bytes_synced_human || '0 B'}</p>
                        ${sync.error ? `<p class="text-red-600 dark:text-red-400"><strong>Error:</strong> ${sync.error}</p>` : ''}
                    </div>
                </div>
            `).join('');
            document.getElementById('nas-history-container').innerHTML = historyHtml || '<p class="text-gray-400 text-center py-4">No sync history</p>';
        }
    } catch (error) {
        console.error('Error loading NAS stats:', error);
        document.getElementById('nas-status-container').innerHTML = '<p class="text-red-500">Failed to load NAS status</p>';
    }
}

async function triggerSync() {
    const confirmed = confirm('Are you sure you want to trigger a NAS sync now? This may take some time depending on the amount of data.');
    if (!confirmed) return;

    try {
        Toast.info('Starting NAS sync...');
        
        const response = await fetch('/api/nas/trigger-sync', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            Toast.success('Sync triggered successfully. Refreshing status...');
            setTimeout(() => loadNasStats(), 2000); // Refresh after 2 seconds
        } else {
            Toast.error('Failed to trigger sync');
        }
    } catch (error) {
        console.error('Error triggering sync:', error);
        Toast.error('Error triggering sync: ' + error.message);
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    // Initialize toast system first
    Toast.init();
    
    initTheme();
    initNavigation();
    initMobileNav();
    initUpload();
    updateDashboard();

    // Initialize processing monitor
    if (typeof ProcessingMonitor !== 'undefined') {
        window.processingMonitor = new ProcessingMonitor();
        window.processingMonitor.start();
    }

    // Initialize audio player
    if (typeof AudioPlayer !== 'undefined') {
        window.audioPlayer = new AudioPlayer();
    }

    // Auto-refresh dashboard every 30 seconds
    setInterval(() => {
        if (!document.getElementById('page-dashboard').classList.contains('hidden')) {
            updateDashboard();
        }
    }, 30000);
    
    // Add counter animation to stats
    initCounterAnimations();
});

// Counter animation for stat values
function initCounterAnimations() {
    const statElements = ['stat-queue', 'stat-library', 'stat-processed', 'stat-failed'];
    
    statElements.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            // Store original value for comparison
            el.dataset.lastValue = el.textContent;
            
            // Create a MutationObserver to watch for value changes
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'childList' || mutation.type === 'characterData') {
                        const newValue = el.textContent;
                        if (newValue !== el.dataset.lastValue) {
                            el.classList.add('counter-animate', 'updating');
                            setTimeout(() => el.classList.remove('updating'), 300);
                            el.dataset.lastValue = newValue;
                        }
                    }
                });
            });
            
            observer.observe(el, { childList: true, characterData: true, subtree: true });
        }
    });
}

// ========================================
// YOUTUBE DOWNLOAD FUNCTIONS
// ========================================

let currentDownloadId = null;
let downloadStatusInterval = null;

async function previewYouTube() {
    const urlInput = document.getElementById('youtube-url');
    const url = urlInput.value.trim();
    
    if (!url) {
        Toast.warning('Please enter a YouTube URL');
        urlInput.focus();
        return;
    }
    
    const previewBtn = document.getElementById('yt-preview-btn');
    const originalContent = previewBtn.innerHTML;
    previewBtn.disabled = true;
    previewBtn.innerHTML = `
        <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Loading...
    `;
    
    try {
        const response = await fetch('/api/youtube/info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch video info');
        }
        
        // Show preview
        const preview = document.getElementById('youtube-preview');
        document.getElementById('yt-thumbnail').src = data.info.thumbnail || '';
        document.getElementById('yt-title').textContent = data.info.title;
        document.getElementById('yt-channel').textContent = data.info.channel;
        document.getElementById('yt-duration').querySelector('span').textContent = data.info.duration_string || 'Unknown';
        document.getElementById('yt-views').querySelector('span').textContent = 
            data.info.view_count ? formatNumber(data.info.view_count) + ' views' : 'Unknown views';
        document.getElementById('yt-filename').textContent = `${data.info.title} - YTDL.mp3`;
        
        preview.classList.remove('hidden');
        Toast.success('Video info loaded');
        
    } catch (error) {
        Toast.error(error.message);
    } finally {
        previewBtn.disabled = false;
        previewBtn.innerHTML = originalContent;
    }
}

async function downloadYouTube() {
    const urlInput = document.getElementById('youtube-url');
    const url = urlInput.value.trim();
    
    if (!url) {
        Toast.warning('Please enter a YouTube URL');
        urlInput.focus();
        return;
    }
    
    const downloadBtn = document.getElementById('yt-download-btn');
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = `
        <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Starting...
    `;
    
    try {
        const response = await fetch('/api/youtube/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to start download');
        }
        
        currentDownloadId = data.download_id;
        
        // Show progress section
        const progressSection = document.getElementById('youtube-progress');
        progressSection.classList.remove('hidden');
        
        // Start polling for status
        startDownloadStatusPolling();
        
        Toast.info('Download started');
        
    } catch (error) {
        Toast.error(error.message);
        resetDownloadButton();
    }
}

function startDownloadStatusPolling() {
    if (downloadStatusInterval) {
        clearInterval(downloadStatusInterval);
    }
    
    downloadStatusInterval = setInterval(async () => {
        if (!currentDownloadId) {
            clearInterval(downloadStatusInterval);
            return;
        }
        
        try {
            const response = await fetch(`/api/youtube/status/${currentDownloadId}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to get status');
            }
            
            updateDownloadProgress(data);
            
            if (data.status === 'completed' || data.status === 'error') {
                clearInterval(downloadStatusInterval);
                downloadStatusInterval = null;
                
                if (data.status === 'completed') {
                    Toast.success(`Downloaded: ${data.filename}`);
                    // Clear the URL input
                    document.getElementById('youtube-url').value = '';
                    // Hide preview
                    document.getElementById('youtube-preview').classList.add('hidden');
                    // Add to history
                    addToDownloadHistory(data);
                } else {
                    Toast.error(`Download failed: ${data.error}`);
                }
                
                // Reset after a delay
                setTimeout(() => {
                    document.getElementById('youtube-progress').classList.add('hidden');
                    resetDownloadButton();
                }, 3000);
                
                currentDownloadId = null;
            }
            
        } catch (error) {
            console.error('Status polling error:', error);
        }
    }, 1000);
}

function updateDownloadProgress(data) {
    document.getElementById('yt-progress-message').textContent = data.message;
    document.getElementById('yt-progress-percent').textContent = `${data.progress}%`;
    document.getElementById('yt-progress-bar').style.width = `${data.progress}%`;
    
    // Update button text based on status
    const downloadBtn = document.getElementById('yt-download-btn');
    if (data.status === 'downloading') {
        downloadBtn.innerHTML = `
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            ${data.progress}%
        `;
    }
}

function resetDownloadButton() {
    const downloadBtn = document.getElementById('yt-download-btn');
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
        </svg>
        Download
    `;
}

function addToDownloadHistory(data) {
    const historyContainer = document.getElementById('youtube-history');
    
    // Remove empty state if present
    const emptyState = historyContainer.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const historyItem = document.createElement('div');
    historyItem.className = 'job-item flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg';
    historyItem.innerHTML = `
        <div class="flex items-center space-x-3 min-w-0">
            <div class="w-10 h-10 bg-gradient-to-br from-red-100 to-red-200 dark:from-red-900 dark:to-red-800 rounded-lg flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
            </div>
            <div class="min-w-0 flex-1">
                <p class="font-medium text-sm truncate">${escapeHtml(data.title || data.filename)}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400">${escapeHtml(data.channel || 'Unknown channel')}</p>
            </div>
        </div>
        <span class="status-badge status-completed flex-shrink-0 ml-2">Completed</span>
    `;
    
    // Add to the beginning
    historyContainer.insertBefore(historyItem, historyContainer.firstChild);
    
    // Limit history display to 10 items
    const items = historyContainer.querySelectorAll('.job-item');
    if (items.length > 10) {
        items[items.length - 1].remove();
    }
}

function formatNumber(num) {
    if (num >= 1000000000) {
        return (num / 1000000000).toFixed(1) + 'B';
    }
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==========================================
// Cookies Management Functions
// ==========================================

/**
 * Check and update the cookies status display
 */
async function checkCookiesStatus() {
    try {
        const response = await fetch('/api/youtube/cookies/status');
        const data = await response.json();
        
        const statusIcon = document.getElementById('cookies-status-icon');
        const statusText = document.getElementById('cookies-status-text');
        const deleteBtn = document.getElementById('delete-cookies-btn');
        
        if (!statusIcon || !statusText) return;
        
        if (data.configured && data.valid) {
            statusIcon.className = 'w-3 h-3 rounded-full bg-green-500';
            statusText.textContent = `Cookies configured (${formatBytes(data.size)})`;
            statusText.className = 'text-sm text-green-600 dark:text-green-400';
            if (deleteBtn) deleteBtn.classList.remove('hidden');
        } else if (data.configured && !data.valid) {
            statusIcon.className = 'w-3 h-3 rounded-full bg-yellow-500';
            statusText.textContent = 'Cookies file exists but may be invalid format';
            statusText.className = 'text-sm text-yellow-600 dark:text-yellow-400';
            if (deleteBtn) deleteBtn.classList.remove('hidden');
        } else {
            statusIcon.className = 'w-3 h-3 rounded-full bg-gray-400';
            statusText.textContent = 'No cookies configured - may get bot detection errors';
            statusText.className = 'text-sm text-gray-500 dark:text-gray-400';
            if (deleteBtn) deleteBtn.classList.add('hidden');
        }
    } catch (error) {
        console.error('Error checking cookies status:', error);
    }
}

/**
 * Format bytes to human readable format
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Upload cookies from file input
 */
async function uploadCookiesFile() {
    const fileInput = document.getElementById('cookies-file-input');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('Please select a cookies.txt file', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/youtube/cookies/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Cookies uploaded successfully!', 'success');
            fileInput.value = '';
            checkCookiesStatus();
        } else {
            showToast(data.error || 'Failed to upload cookies', 'error');
        }
    } catch (error) {
        console.error('Error uploading cookies:', error);
        showToast('Error uploading cookies: ' + error.message, 'error');
    }
}

/**
 * Upload cookies from text input
 */
async function uploadCookiesText() {
    const textInput = document.getElementById('cookies-text-input');
    if (!textInput || !textInput.value.trim()) {
        showToast('Please paste cookies content', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/youtube/cookies/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ cookies_text: textInput.value })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Cookies saved successfully!', 'success');
            textInput.value = '';
            checkCookiesStatus();
        } else {
            showToast(data.error || 'Failed to save cookies', 'error');
        }
    } catch (error) {
        console.error('Error saving cookies:', error);
        showToast('Error saving cookies: ' + error.message, 'error');
    }
}

/**
 * Delete cookies file
 */
async function deleteCookies() {
    if (!confirm('Are you sure you want to delete the cookies file?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/youtube/cookies/delete', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showToast('Cookies deleted', 'success');
            checkCookiesStatus();
        } else {
            showToast(data.error || 'Failed to delete cookies', 'error');
        }
    } catch (error) {
        console.error('Error deleting cookies:', error);
        showToast('Error deleting cookies: ' + error.message, 'error');
    }
}

// ============================================================
// PO Token Provider Functions (Automatic Bot Bypass)
// ============================================================

/**
 * Check PO Token provider status and update UI
 */
async function checkPOTProviderStatus() {
    const statusIcon = document.getElementById('pot-status-icon');
    const statusText = document.getElementById('pot-status-text');
    
    if (!statusIcon || !statusText) return;
    
    try {
        const response = await fetch('/api/youtube/pot-provider/status');
        
        if (!response.ok) {
            statusIcon.className = 'w-3 h-3 rounded-full bg-gray-400';
            statusText.textContent = 'Unable to check PO Token provider status';
            return;
        }
        
        const data = await response.json();
        
        if (data.available) {
            // Provider is running
            statusIcon.className = 'w-3 h-3 rounded-full bg-green-500';
            statusText.textContent = data.message || 'PO Token provider is active';
            statusText.className = 'text-sm text-green-600 dark:text-green-400';
        } else {
            // Provider not available
            statusIcon.className = 'w-3 h-3 rounded-full bg-yellow-500';
            statusText.textContent = data.message || 'PO Token provider not available';
            statusText.className = 'text-sm text-yellow-600 dark:text-yellow-400';
            
            // Show error details if available
            if (data.error) {
                console.warn('PO Token provider error:', data.error);
            }
        }
        
    } catch (error) {
        console.error('Error checking PO Token provider status:', error);
        statusIcon.className = 'w-3 h-3 rounded-full bg-gray-400';
        statusText.textContent = 'Unable to check status';
        statusText.className = 'text-sm text-gray-600 dark:text-gray-400';
    }
}

// Check cookies and PO Token provider status when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Check cookies status after a short delay to ensure page is ready
    setTimeout(checkCookiesStatus, 500);
    // Check PO Token provider status
    setTimeout(checkPOTProviderStatus, 700);
});

// Make YouTube functions globally available
window.previewYouTube = previewYouTube;
window.downloadYouTube = downloadYouTube;
window.uploadCookiesFile = uploadCookiesFile;
window.uploadCookiesText = uploadCookiesText;
window.deleteCookies = deleteCookies;
window.checkCookiesStatus = checkCookiesStatus;
window.checkPOTProviderStatus = checkPOTProviderStatus;

