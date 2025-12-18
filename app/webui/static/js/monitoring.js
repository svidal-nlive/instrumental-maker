/**
 * NAS Monitoring Dashboard
 * Provides real-time monitoring of NAS sync operations and job artifacts
 */

class NASMonitor {
    constructor() {
        this.pollInterval = 5000; // 5 seconds
        this.pollTimer = null;
        this.currentJobId = null;
    }

    /**
     * Start monitoring NAS sync operations
     */
    startMonitoring() {
        this.loadSyncStatus();
        this.loadSyncHealth();
        this.loadRecentEvents();
        
        // Set up auto-refresh
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.pollTimer = setInterval(() => {
            this.loadSyncStatus();
            this.loadSyncHealth();
        }, this.pollInterval);
    }

    /**
     * Stop monitoring
     */
    stopMonitoring() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    /**
     * Load sync status and statistics
     */
    async loadSyncStatus() {
        try {
            const response = await fetch('/api/nas-sync/status');
            const data = await response.json();

            // Update statistics
            document.getElementById('stat-successful').textContent = data.statistics.successful_syncs || 0;
            document.getElementById('stat-failed').textContent = data.statistics.failed_syncs || 0;
            document.getElementById('stat-skipped').textContent = data.statistics.skipped_syncs || 0;
            
            const mb = ((data.statistics.total_bytes || 0) / 1024 / 1024).toFixed(2);
            document.getElementById('stat-data').textContent = `${mb} MB`;

            // Update current method
            if (data.current_method) {
                document.getElementById('current-sync-method').textContent = data.current_method;
            }

        } catch (error) {
            console.error('Error loading sync status:', error);
        }
    }

    /**
     * Load NAS sync health information
     */
    async loadSyncHealth() {
        try {
            const response = await fetch('/api/nas-sync/health');
            const data = await response.json();

            // Update health status
            const statusEl = document.getElementById('sync-status-value');
            const statusBadge = {
                'healthy': '<span class="text-green-600 dark:text-green-400 flex items-center gap-1"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>Healthy</span>',
                'warning': '<span class="text-yellow-600 dark:text-yellow-400 flex items-center gap-1"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>Warning</span>',
                'unknown': '<span class="text-gray-600 dark:text-gray-400 flex items-center gap-1"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>Unknown</span>',
                'error': '<span class="text-red-600 dark:text-red-400 flex items-center gap-1"><svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg>Error</span>'
            };
            statusEl.innerHTML = statusBadge[data.status] || statusBadge['unknown'];

            // Update last sync time
            if (data.last_sync) {
                const lastSyncEl = document.getElementById('last-sync-time');
                const lastTime = new Date(data.last_sync);
                lastSyncEl.textContent = this.formatTimeAgo(lastTime);
            }

            // Update total syncs
            document.getElementById('total-syncs-value').textContent = data.total_events || 0;

        } catch (error) {
            console.error('Error loading sync health:', error);
        }
    }

    /**
     * Load recent sync events
     */
    async loadRecentEvents() {
        try {
            const response = await fetch('/api/nas-sync/logs?limit=20');
            const data = await response.json();

            const eventsList = document.getElementById('recent-events-list');
            if (data.logs && data.logs.length > 0) {
                eventsList.innerHTML = data.logs.map(event => this.renderEventCard(event)).join('');
            } else {
                eventsList.innerHTML = '<p class="text-center text-gray-500 dark:text-gray-400 text-sm py-8">No events recorded yet</p>';
            }

        } catch (error) {
            console.error('Error loading recent events:', error);
            document.getElementById('recent-events-list').innerHTML = 
                `<div class="text-center text-red-500 dark:text-red-400 text-sm py-8">Error loading events</div>`;
        }
    }

    /**
     * Render an event card
     */
    renderEventCard(event) {
        const statusColors = {
            'success': 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300',
            'failed': 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300',
            'skipped': 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800 text-yellow-700 dark:text-yellow-300',
            'processing': 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'
        };

        const statusClass = statusColors[event.status] || statusColors['processing'];
        const timestamp = new Date(event.timestamp);

        return `
            <div class="p-3 rounded-lg border ${statusClass}">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="font-semibold text-xs uppercase tracking-wide">
                            ${event.event_type === 'manifest_processed' ? 'Sync' : 'Artifact'} - ${event.status}
                        </div>
                        ${event.sync_method ? `<div class="text-xs mt-1">Method: <span class="font-mono">${event.sync_method}</span></div>` : ''}
                        ${event.message ? `<div class="text-xs mt-1">${escapeHtml(event.message)}</div>` : ''}
                    </div>
                    <div class="text-xs whitespace-nowrap flex-shrink-0">
                        ${this.formatTimeAgo(timestamp)}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Format time as "time ago" string
     */
    formatTimeAgo(date) {
        const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    }

    /**
     * Load job artifacts
     */
    async loadJobArtifacts(jobId) {
        if (!jobId || jobId.trim().length === 0) {
            document.getElementById('job-artifacts-container').innerHTML = 
                '<p class="text-center text-gray-500 dark:text-gray-400 text-sm py-8">Type a job ID to view artifacts...</p>';
            return;
        }

        const container = document.getElementById('job-artifacts-container');
        container.innerHTML = '<div class="flex items-center justify-center py-8"><svg class="animate-spin h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>';

        try {
            const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/artifacts`);
            if (!response.ok) {
                if (response.status === 404) {
                    container.innerHTML = '<p class="text-center text-orange-500 dark:text-orange-400 text-sm py-8">Job not found</p>';
                } else {
                    container.innerHTML = '<p class="text-center text-red-500 dark:text-red-400 text-sm py-8">Error loading artifacts</p>';
                }
                return;
            }

            const data = await response.json();
            if (data.artifacts && data.artifacts.length > 0) {
                container.innerHTML = data.artifacts.map(artifact => this.renderArtifactCard(artifact)).join('');
            } else {
                container.innerHTML = '<p class="text-center text-gray-500 dark:text-gray-400 text-sm py-8">No artifacts found</p>';
            }

        } catch (error) {
            console.error('Error loading artifacts:', error);
            container.innerHTML = '<p class="text-center text-red-500 dark:text-red-400 text-sm py-8">Error loading artifacts</p>';
        }
    }

    /**
     * Render an artifact card
     */
    renderArtifactCard(artifact) {
        const size = (artifact.total_size / 1024 / 1024).toFixed(2);
        const fileCount = artifact.files ? artifact.files.length : 0;

        const typeIcons = {
            'audio': '🎵',
            'image': '🖼️',
            'metadata': '📄',
            'other': '📦'
        };

        return `
            <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="font-semibold flex items-center gap-2">
                            <span>${typeIcons[artifact.type] || '📦'}</span>
                            <span class="truncate">${escapeHtml(artifact.name)}</span>
                        </div>
                        <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            ${fileCount} file${fileCount !== 1 ? 's' : ''} • ${size} MB
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// Create global monitor instance
let nasMonitor = new NASMonitor();

/**
 * Load NAS monitoring data
 */
async function loadNASMonitoring() {
    nasMonitor.startMonitoring();
    nasMonitor.loadRecentEvents();
}

/**
 * Test NAS connectivity
 */
async function testNASConnectivity() {
    const btn = document.getElementById('test-connectivity-btn');
    const resultEl = document.getElementById('connectivity-result');
    
    btn.disabled = true;
    btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Testing...';

    try {
        const response = await fetch('/api/nas-sync/test-connectivity', {
            method: 'POST'
        });
        const data = await response.json();

        if (data.available) {
            resultEl.innerHTML = `
                <div class="flex items-start gap-3 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                    <svg class="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>
                    </svg>
                    <div class="text-sm">
                        <p class="font-semibold text-green-800 dark:text-green-300">${escapeHtml(data.method)} Connected</p>
                        <p class="text-green-700 dark:text-green-400 mt-1">${escapeHtml(data.message)}</p>
                    </div>
                </div>
            `;
        } else {
            resultEl.innerHTML = `
                <div class="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                    <svg class="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                    </svg>
                    <div class="text-sm">
                        <p class="font-semibold text-red-800 dark:text-red-300">${escapeHtml(data.method)} Connection Failed</p>
                        <p class="text-red-700 dark:text-red-400 mt-1">${escapeHtml(data.message)}</p>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        resultEl.innerHTML = `
            <div class="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <svg class="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                <div class="text-sm">
                    <p class="font-semibold text-red-800 dark:text-red-300">Connection Test Failed</p>
                    <p class="text-red-700 dark:text-red-400 mt-1">${escapeHtml(error.message)}</p>
                </div>
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> Test Connection';
    }
}

/**
 * Set up job search
 */
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('job-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            nasMonitor.loadJobArtifacts(e.target.value);
        });
    }
});

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
