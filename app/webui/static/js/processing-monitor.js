// Processing Monitor - Real-time status and progress tracking

class ProcessingMonitor {
    constructor() {
        this.updateInterval = null;
        this.refreshRate = 2000; // 2 seconds
    }

    start() {
        this.update();
        this.updateInterval = setInterval(() => this.update(), this.refreshRate);
    }

    stop() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    async update() {
        try {
            const [status, config, history] = await Promise.all([
                fetch('/api/processing/status').then(r => r.json()),
                fetch('/api/processing/config').then(r => r.json()),
                fetch('/api/processing/history?limit=10').then(r => r.json())
            ]);

            this.updateStatusUI(status, config);
            this.updateHistoryUI(history);
        } catch (error) {
            console.error('Error updating processing monitor:', error);
        }
    }

    updateStatusUI(status, config) {
        const container = document.getElementById('processing-status');
        if (!container) return;

        const processor = status.processor;
        const currentJob = status.current_job;

        // Update processor status indicator
        const statusBadge = container.querySelector('#processor-status');
        if (statusBadge) {
            if (processor.running) {
                statusBadge.className = 'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
                statusBadge.innerHTML = `
                    <svg class="w-2 h-2 mr-1.5 animate-pulse" fill="currentColor" viewBox="0 0 8 8">
                        <circle cx="4" cy="4" r="3" />
                    </svg>
                    Active
                `;
            } else {
                statusBadge.className = 'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
                statusBadge.innerHTML = `
                    <svg class="w-2 h-2 mr-1.5" fill="currentColor" viewBox="0 0 8 8">
                        <circle cx="4" cy="4" r="3" />
                    </svg>
                    Idle
                `;
            }
        }

        // Update current job display
        const jobContainer = container.querySelector('#current-job');
        if (jobContainer) {
            if (currentJob && processor.running) {
                const elapsed = this.formatDuration(currentJob.elapsed);
                const progress = currentJob.progress_percent || 0;
                
                jobContainer.innerHTML = `
                    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 border border-gray-200 dark:border-gray-700">
                        <div class="flex items-start justify-between mb-3">
                            <div class="flex-1">
                                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">
                                    Processing: ${currentJob.source_file || 'Unknown file'}
                                </h3>
                                <p class="text-xs text-gray-500 dark:text-gray-400">
                                    Stage: <span class="font-medium capitalize">${currentJob.stage}</span> • 
                                    Elapsed: <span class="font-medium">${elapsed}</span>
                                </p>
                            </div>
                            ${!currentJob.is_active ? `
                                <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                                    <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                    </svg>
                                    Idle ${Math.floor(currentJob.idle_seconds)}s
                                </span>
                            ` : ''}
                        </div>
                        
                        <!-- Progress Bar -->
                        <div class="space-y-2">
                            <div class="flex items-center justify-between text-xs">
                                <span class="text-gray-600 dark:text-gray-400">
                                    Chunk ${currentJob.completed_chunks + 1}/${currentJob.total_chunks}
                                </span>
                                <span class="font-semibold text-primary-600 dark:text-primary-400">
                                    ${progress}%
                                </span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                                <div class="bg-gradient-to-r from-primary-500 to-accent-500 h-2.5 rounded-full transition-all duration-500 ease-out" 
                                     style="width: ${progress}%"></div>
                            </div>
                            
                            <!-- Chunk indicators -->
                            <div class="flex gap-1 mt-2">
                                ${Array.from({length: currentJob.total_chunks}, (_, i) => {
                                    const completed = i < currentJob.completed_chunks;
                                    const current = i === currentJob.completed_chunks;
                                    return `
                                        <div class="flex-1 h-1 rounded-full ${
                                            completed ? 'bg-green-500' : 
                                            current ? 'bg-blue-500 animate-pulse' : 
                                            'bg-gray-300 dark:bg-gray-600'
                                        }" title="Chunk ${i + 1}"></div>
                                    `;
                                }).join('')}
                            </div>
                        </div>

                        <!-- Config info -->
                        <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                            <span class="inline-flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                                </svg>
                                ${config.model}
                            </span>
                            <span class="inline-flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                                </svg>
                                ${config.device.toUpperCase()}
                            </span>
                            <span class="inline-flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                                ${Math.floor(config.timeout_sec / 60)}min timeout
                            </span>
                            <span class="inline-flex items-center">
                                <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                                </svg>
                                ${config.max_retries} retries
                            </span>
                        </div>
                    </div>
                `;
            } else {
                jobContainer.innerHTML = `
                    <div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-8 text-center border-2 border-dashed border-gray-300 dark:border-gray-700">
                        <svg class="w-12 h-12 mx-auto text-gray-400 dark:text-gray-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>
                        </svg>
                        <p class="text-gray-500 dark:text-gray-400 font-medium">No active processing</p>
                        <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Upload files to begin</p>
                    </div>
                `;
            }
        }
    }

    updateHistoryUI(history) {
        const container = document.getElementById('processing-history');
        if (!container || !history || history.length === 0) {
            if (container) {
                container.innerHTML = `
                    <div class="text-center py-8 text-gray-500 dark:text-gray-400">
                        <p>No processing history yet</p>
                    </div>
                `;
            }
            return;
        }

        container.innerHTML = history.map(item => {
            const date = new Date(item.timestamp * 1000);
            const duration = this.formatDuration(item.processing_time_sec);
            const ratio = (item.processing_time_sec / item.duration_sec).toFixed(1);
            
            return `
                <div class="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
                    <div class="flex items-start justify-between">
                        <div class="flex-1 min-w-0">
                            <h4 class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                                ${item.title || 'Unknown'}
                            </h4>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                ${item.artist || 'Unknown'} • ${item.album || 'Unknown'}
                            </p>
                            <div class="flex flex-wrap gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400">
                                <span>${this.formatDuration(item.duration_sec)} audio</span>
                                <span>•</span>
                                <span>${duration} processing</span>
                                <span>•</span>
                                <span>${ratio}x realtime</span>
                                <span>•</span>
                                <span>${item.chunk_count} chunks</span>
                            </div>
                        </div>
                        <div class="ml-4 text-right">
                            <span class="text-xs text-gray-400 dark:text-gray-500">
                                ${date.toLocaleTimeString()}
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    formatDuration(seconds) {
        if (!seconds || seconds < 0) return '0s';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    }
}

// Initialize on page load
let processingMonitor;
document.addEventListener('DOMContentLoaded', () => {
    processingMonitor = new ProcessingMonitor();
    processingMonitor.start();
});
