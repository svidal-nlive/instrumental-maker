/**
 * Dashboard Status Monitor
 * Handles real-time status updates for queues, processing, and recent jobs
 */

class DashboardStatusMonitor {
    constructor(updateInterval = 2000) {
        this.updateInterval = updateInterval;
        this.statusPoller = null;
        this.queueStatus = {};
        this.recentJobs = [];
        this.currentJob = null;
    }

    init() {
        // Start polling status
        this.startPolling();
        
        // Initial update
        this.updateStatus();
    }

    startPolling() {
        this.statusPoller = setInterval(() => this.updateStatus(), this.updateInterval);
    }

    stopPolling() {
        if (this.statusPoller) {
            clearInterval(this.statusPoller);
            this.statusPoller = null;
        }
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            
            // Update queue statistics
            this.updateQueueStats(data);
            
            // Update processor status
            this.updateProcessorStatus(data);
            
            // Load recent jobs
            await this.loadRecentJobs();
            
            // Update UI elements
            this.render();
        } catch (error) {
            console.error('Failed to update status:', error);
            this.showError('Failed to update dashboard status');
        }
    }

    updateQueueStats(data) {
        this.queueStatus = data.queues || {};
        
        const totalQueue = this.queueStatus.total || 0;
        const youtubeAudio = this.queueStatus.youtube_audio || 0;
        const youtubeVideo = this.queueStatus.youtube_video || 0;
        const other = this.queueStatus.other || 0;
        
        // Update queue stat card
        const queueElement = document.getElementById('stat-queue');
        if (queueElement) {
            queueElement.textContent = totalQueue;
            queueElement.parentElement.parentElement.classList.toggle('opacity-50', totalQueue === 0);
        }
        
        // Update queue details in header tooltip
        const details = [
            `YouTube Audio: ${youtubeAudio}`,
            `YouTube Video: ${youtubeVideo}`,
            `Other: ${other}`
        ];
        
        if (queueElement) {
            queueElement.title = details.join('\n');
        }
    }

    updateProcessorStatus(data) {
        if (!data.processing) return;
        
        const { pid, running } = data.processing;
        const statusElement = document.getElementById('processor-status');
        
        if (statusElement) {
            if (running) {
                statusElement.innerHTML = `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs md:text-sm font-medium bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100">
                        <span class="w-2 h-2 rounded-full bg-green-600 dark:bg-green-400 mr-2 animate-pulse"></span>
                        Processing (PID: ${pid})
                    </span>
                `;
            } else {
                statusElement.innerHTML = `
                    <span class="inline-flex items-center px-3 py-1 rounded-full text-xs md:text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100">
                        <span class="w-2 h-2 rounded-full bg-gray-400 mr-2"></span>
                        Idle
                    </span>
                `;
            }
        }
        
        // Update current job status
        this.updateCurrentJobStatus(running);
    }

    updateCurrentJobStatus(isRunning) {
        const currentJobElement = document.getElementById('current-job');
        if (!currentJobElement) return;
        
        if (isRunning) {
            currentJobElement.innerHTML = `
                <div class="flex items-center justify-between p-4 bg-gradient-to-r from-primary-50 to-accent-50 dark:from-primary-900/20 dark:to-accent-900/20 rounded-lg border border-primary-200 dark:border-primary-800">
                    <div class="flex items-center space-x-3">
                        <div class="w-3 h-3 rounded-full bg-green-500 animate-pulse"></div>
                        <div>
                            <p class="text-sm font-semibold text-gray-900 dark:text-gray-100">Processing in progress...</p>
                            <p class="text-xs text-gray-600 dark:text-gray-400">Check back soon for status updates</p>
                        </div>
                    </div>
                    <svg class="w-5 h-5 text-primary-600 dark:text-primary-400 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                </div>
            `;
        } else {
            currentJobElement.innerHTML = `
                <div class="flex items-center justify-center py-8 text-gray-400">
                    <div class="text-center">
                        <svg class="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                        <p class="text-sm text-gray-600 dark:text-gray-400">No processing currently running</p>
                    </div>
                </div>
            `;
        }
    }

    async loadRecentJobs() {
        try {
            const response = await fetch('/api/jobs/recent?limit=10');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            this.recentJobs = data.jobs || [];
        } catch (error) {
            console.error('Failed to load recent jobs:', error);
            this.recentJobs = [];
        }
    }

    render() {
        this.renderRecentJobs();
    }

    renderRecentJobs() {
        const container = document.getElementById('recent-jobs');
        if (!container) return;
        
        if (this.recentJobs.length === 0) {
            container.innerHTML = `
                <div class="flex items-center justify-center py-8 text-gray-400">
                    <div class="text-center">
                        <svg class="w-12 h-12 mx-auto mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                        </svg>
                        <p class="text-sm">No jobs processed yet</p>
                    </div>
                </div>
            `;
            return;
        }
        
        const jobsHtml = this.recentJobs.map(job => {
            const statusColor = this.getStatusColor(job.status);
            const statusIcon = this.getStatusIcon(job.status);
            const timeAgo = this.formatTimeAgo(new Date(job.completed_at));
            
            return `
                <div class="flex items-center justify-between p-3 md:p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer group" data-job-id="${job.job_id}">
                    <div class="flex items-center space-x-3 md:space-x-4 flex-1 min-w-0">
                        <div class="w-10 h-10 rounded-lg ${statusColor} flex items-center justify-center flex-shrink-0">
                            ${statusIcon}
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">${this.formatJobId(job.job_id)}</p>
                            <p class="text-xs text-gray-500 dark:text-gray-400">${job.source} • ${job.job_type} • ${job.artifacts_count || 0} artifacts</p>
                        </div>
                    </div>
                    <div class="text-right flex-shrink-0">
                        <p class="text-xs font-medium text-gray-600 dark:text-gray-400">${timeAgo}</p>
                        <p class="text-xs text-gray-500 dark:text-gray-500 capitalize">${job.status}</p>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = jobsHtml;
    }

    getStatusColor(status) {
        switch (status) {
            case 'success':
                return 'bg-green-100 dark:bg-green-900/30';
            case 'failed':
                return 'bg-red-100 dark:bg-red-900/30';
            case 'skipped':
                return 'bg-yellow-100 dark:bg-yellow-900/30';
            default:
                return 'bg-gray-100 dark:bg-gray-700';
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'success':
                return '<svg class="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            case 'failed':
                return '<svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
            case 'skipped':
                return '<svg class="w-5 h-5 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4v2m0 4v2M7 5h10a2 2 0 012 2v10a2 2 0 01-2 2H7a2 2 0 01-2-2V7a2 2 0 012-2z"></path></svg>';
            default:
                return '<svg class="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
        }
    }

    formatJobId(jobId) {
        if (!jobId) return 'Unknown';
        return jobId.length > 20 ? jobId.substring(0, 20) + '...' : jobId;
    }

    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffSecs < 60) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    showError(message) {
        const toast = document.createElement('div');
        toast.className = 'fixed top-4 right-4 bg-red-500 text-white px-4 py-3 rounded-lg shadow-lg';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }
}

// Initialize dashboard monitor when page loads
const dashboardMonitor = new DashboardStatusMonitor(2000);

// Add to existing page initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        dashboardMonitor.init();
    });
} else {
    dashboardMonitor.init();
}
