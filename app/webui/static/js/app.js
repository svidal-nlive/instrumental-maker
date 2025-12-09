// Instrumental Maker Web UI - Main JavaScript

// Mobile Sidebar Toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
    
    // Prevent body scroll when sidebar is open
    document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
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
        logs: { title: 'Logs', subtitle: 'Real-time processing logs and events' }
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
            <div class="text-center py-8 text-gray-400">
                <p>No recent jobs</p>
            </div>
        `;
        return;
    }

    container.innerHTML = jobs.slice(0, 10).map(job => `
        <div class="flex items-center justify-between p-3 md:p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors gap-3">
            <div class="flex items-center space-x-3 md:space-x-4 flex-1 min-w-0">
                <div class="w-8 h-8 md:w-10 md:h-10 rounded-lg shrink-0 ${job.status === 'completed' ? 'bg-green-100 dark:bg-green-900' : 'bg-red-100 dark:bg-red-900'} flex items-center justify-center">
                    ${job.status === 'completed' 
                        ? '<svg class="w-4 h-4 md:w-5 md:h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
                        : '<svg class="w-4 h-4 md:w-5 md:h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
                    }
                </div>
                <div class="flex-1 min-w-0">
                    <p class="font-medium text-sm md:text-base text-gray-900 dark:text-gray-100 truncate">${job.filename}</p>
                    <p class="text-xs md:text-sm text-gray-500 dark:text-gray-400 truncate">${job.artist} - ${job.album}</p>
                </div>
            </div>
            <div class="text-right shrink-0">
                <p class="text-xs md:text-sm text-gray-500 dark:text-gray-400">${formatTimestamp(job.timestamp)}</p>
                ${job.duration ? `<p class="text-xs text-gray-400">${Math.round(job.duration)}s</p>` : ''}
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
            alert(result.message || 'Processing history cleared successfully');
            // Reload recent jobs if available
            if (typeof loadRecentJobs === 'function') {
                loadRecentJobs();
            }
        } else {
            alert('Failed to clear processing history');
        }
    } catch (error) {
        console.error('Error clearing history:', error);
        alert('Error clearing processing history: ' + error.message);
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
            alert(result.message || 'Processing logs cleared successfully');
            // Reload logs if available
            if (typeof loadLogs === 'function') {
                loadLogs();
            }
        } else {
            alert('Failed to clear processing logs');
        }
    } catch (error) {
        console.error('Error clearing logs:', error);
        alert('Error clearing processing logs: ' + error.message);
    }
}

// Upload handling
function initUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-primary-500', 'dark:border-primary-400');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-primary-500', 'dark:border-primary-400');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-primary-500', 'dark:border-primary-400');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
}

async function handleFiles(files) {
    for (const file of files) {
        await uploadFile(file);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            console.log('File uploaded:', file.name);
            // Show success notification
        } else {
            console.error('Upload failed:', file.name);
        }
    } catch (error) {
        console.error('Upload error:', error);
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

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
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
});
