/**
 * Settings Configuration Manager
 * Handles loading, displaying, and updating system configuration
 */

class SettingsManager {
    constructor() {
        this.config = {};
        this.categories = {};
        this.currentTab = 'variant-generation';
        this.initialized = false;
    }

    async init() {
        if (this.initialized) return;
        
        // Load configuration categories
        await this.loadConfigCategories();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Render initial tab
        this.switchTab('variant-generation');
        
        this.initialized = true;
    }

    async loadConfigCategories() {
        try {
            const response = await fetch('/settings/api/config-categories');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            this.categories = await response.json();
            console.log('Configuration categories loaded:', this.categories);
        } catch (error) {
            console.error('Failed to load configuration categories:', error);
            this.showError('Failed to load settings configuration');
        }
    }

    setupEventListeners() {
        // Tab buttons
        document.querySelectorAll('.settings-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
            });
        });
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.settings-tab-btn').forEach(btn => {
            if (btn.dataset.tab === tabName) {
                btn.classList.remove('border-transparent', 'text-gray-600', 'dark:text-gray-400');
                btn.classList.add('border-primary-600', 'text-primary-600', 'dark:text-primary-400');
            } else {
                btn.classList.add('border-transparent', 'text-gray-600', 'dark:text-gray-400');
                btn.classList.remove('border-primary-600', 'text-primary-600', 'dark:text-primary-400');
            }
        });

        this.currentTab = tabName;
        this.renderTabContent(tabName);
    }

    getCategoryFromTab(tabName) {
        const tabToCategoryMap = {
            'variant-generation': 'Variant Generation',
            'demucs': 'Demucs',
            'audio': 'Audio Processing',
            'youtube': 'YouTube Download',
            'nas-sync': 'NAS Synchronization',
            'queue': 'Queue Processing'
        };
        return tabToCategoryMap[tabName];
    }

    renderTabContent(tabName) {
        const categoryName = this.getCategoryFromTab(tabName);
        const category = this.categories[categoryName];
        const content = document.getElementById('settings-content');

        if (!category) {
            content.innerHTML = '<p class="text-red-600">Category not found</p>';
            return;
        }

        let html = `
            <div class="space-y-4">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">${categoryName}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-400">${category.description}</p>
                </div>
                <form id="settings-form-${tabName}" class="space-y-4">
        `;

        Object.entries(category.variables).forEach(([varName, config]) => {
            html += this.renderFormField(varName, config);
        });

        html += `
                    <div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
                        <button type="button" class="reset-btn px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors" data-tab="${tabName}">
                            Reset to Defaults
                        </button>
                        <button type="submit" class="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors">
                            Save Changes
                        </button>
                    </div>
                </form>
            </div>
        `;

        content.innerHTML = html;

        // Set up form submission
        const form = document.getElementById(`settings-form-${tabName}`);
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e, tabName));
        }

        // Set up reset buttons
        document.querySelectorAll('.reset-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleResetTab(e, btn.dataset.tab));
        });
    }

    renderFormField(varName, config) {
        const dataType = config.data_type;
        const currentValue = config.value;
        const isDefault = config.is_default;
        
        let fieldHtml = `
            <div class="form-group p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex-1">
                        <label for="${varName}" class="block text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
                            ${this.formatVariableName(varName)}
                        </label>
                        <p class="text-xs text-gray-600 dark:text-gray-400">${config.description}</p>
                    </div>
                    ${isDefault ? '<span class="ml-2 px-2 py-1 text-xs bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded">default</span>' : ''}
                </div>
        `;

        // Render appropriate input based on data type
        if (dataType === 'bool') {
            fieldHtml += `
                <div class="mt-3">
                    <label class="flex items-center cursor-pointer">
                        <input type="checkbox" name="${varName}" id="${varName}" class="w-4 h-4 rounded border-gray-300 text-primary-600 cursor-pointer" ${currentValue ? 'checked' : ''}>
                        <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">${currentValue ? 'Enabled' : 'Disabled'}</span>
                    </label>
                </div>
            `;
        } else if (dataType === 'int') {
            fieldHtml += `
                <input type="number" name="${varName}" id="${varName}" value="${currentValue}" class="mt-3 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded-lg text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all" step="1">
            `;
        } else if (dataType === 'float') {
            fieldHtml += `
                <input type="number" name="${varName}" id="${varName}" value="${currentValue}" class="mt-3 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded-lg text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all" step="0.01">
            `;
        } else {
            // String type - check for special options
            const options = this.getSelectOptions(varName);
            if (options) {
                fieldHtml += `
                    <select name="${varName}" id="${varName}" class="mt-3 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded-lg text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all">
                        ${options.map(opt => `<option value="${opt}" ${opt === currentValue ? 'selected' : ''}>${opt}</option>`).join('')}
                    </select>
                `;
            } else {
                fieldHtml += `
                    <input type="text" name="${varName}" id="${varName}" value="${currentValue}" class="mt-3 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 rounded-lg text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all">
                `;
            }
        }

        fieldHtml += `
            </div>
        `;

        return fieldHtml;
    }

    getSelectOptions(varName) {
        const selectOptions = {
            'DEMUCS_DEVICE': ['cpu', 'cuda'],
            'YTDL_MODE': ['audio', 'video', 'both'],
            'YTDL_AUDIO_FORMAT': ['m4a', 'flac', 'mp3', 'wav'],
            'MP3_ENCODING': ['cbr320', 'cbr256', 'cbr192', 'vbr9', 'vbr8', 'vbr7'],
            'NAS_SYNC_METHOD': ['rsync', 's3', 'scp', 'local'],
            'MODEL': ['htdemucs', 'htdemucs_ft', 'htdemucs_6s']
        };
        return selectOptions[varName] || null;
    }

    formatVariableName(varName) {
        return varName
            .replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    }

    async handleFormSubmit(event, tabName) {
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        const changes = [];
        const validationErrors = [];

        for (const [key, value] of formData.entries()) {
            const category = this.getCategoryFromTab(tabName);
            const config = this.categories[category].variables[key];
            
            if (!config) continue;

            let actualValue = value;
            
            // Convert value based on data type
            if (config.data_type === 'bool') {
                actualValue = form.elements[key].checked;
            } else if (config.data_type === 'int') {
                actualValue = parseInt(value, 10);
                if (isNaN(actualValue)) {
                    validationErrors.push(`${this.formatVariableName(key)} must be a valid integer`);
                    continue;
                }
                // Validate ranges
                if (key === 'DEMUCS_JOBS' && actualValue < 1) {
                    validationErrors.push('DEMUCS_JOBS must be at least 1');
                    continue;
                }
                if (key === 'SAMPLE_RATE' && actualValue < 8000) {
                    validationErrors.push('SAMPLE_RATE must be at least 8000 Hz');
                    continue;
                }
                if (key === 'CHUNK_OVERLAP_SEC' && actualValue < 0) {
                    validationErrors.push('CHUNK_OVERLAP_SEC cannot be negative');
                    continue;
                }
                if (key === 'CROSSFADE_MS' && actualValue < 0) {
                    validationErrors.push('CROSSFADE_MS cannot be negative');
                    continue;
                }
                if (key === 'NAS_POLL_INTERVAL_SEC' && actualValue < 1) {
                    validationErrors.push('NAS_POLL_INTERVAL_SEC must be at least 1 second');
                    continue;
                }
            } else if (config.data_type === 'float') {
                actualValue = parseFloat(value);
                if (isNaN(actualValue)) {
                    validationErrors.push(`${this.formatVariableName(key)} must be a valid number`);
                    continue;
                }
                // Validate ranges
                if (key === 'YTDL_DURATION_TOL_SEC' && actualValue < 0) {
                    validationErrors.push('Duration tolerance must not be negative');
                    continue;
                }
                if (key === 'YTDL_DURATION_TOL_PCT' && (actualValue < 0 || actualValue > 1)) {
                    validationErrors.push('Duration tolerance percentage must be between 0 and 1');
                    continue;
                }
            } else if (config.data_type === 'str') {
                // String validation
                if (!value || value.trim().length === 0) {
                    validationErrors.push(`${this.formatVariableName(key)} cannot be empty`);
                    continue;
                }
                // Special validation for model names
                if (key === 'MODEL') {
                    const validModels = ['htdemucs', 'htdemucs_ft', 'htdemucs_6s'];
                    if (!validModels.includes(value)) {
                        validationErrors.push(`Invalid model: ${value}. Valid options are: ${validModels.join(', ')}`);
                        continue;
                    }
                }
            }

            // Only track if changed
            if (actualValue !== config.value) {
                changes.push({ key, value: actualValue });
            }
        }

        // Show validation errors if any
        if (validationErrors.length > 0) {
            this.showError(validationErrors.join('; '));
            return;
        }

        if (changes.length === 0) {
            this.showInfo('No changes detected');
            return;
        }

        // Submit changes
        let successCount = 0;
        let failedKeys = [];
        for (const change of changes) {
            const success = await this.updateConfig(change.key, change.value);
            if (success) {
                successCount++;
            } else {
                failedKeys.push(change.key);
            }
        }

        if (successCount === changes.length) {
            this.showSuccess(`Saved ${successCount} configuration change${successCount !== 1 ? 's' : ''}`);
            // Reload settings
            await this.loadConfigCategories();
            this.renderTabContent(tabName);
        } else if (successCount > 0) {
            this.showError(`Saved ${successCount}/${changes.length} changes. Failed: ${failedKeys.join(', ')}`);
        } else {
            this.showError('Failed to save configuration changes');
        }
    }

    async updateConfig(key, value) {
        try {
            const response = await fetch(`/api/config/${key}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return true;
        } catch (error) {
            console.error(`Failed to update ${key}:`, error);
            return false;
        }
    }

    async handleResetTab(event, tabName) {
        event.preventDefault();
        
        if (!confirm('Reset all settings in this category to their defaults?')) {
            return;
        }

        const categoryName = this.getCategoryFromTab(tabName);
        const category = this.categories[categoryName];
        let successCount = 0;

        for (const varName of Object.keys(category.variables)) {
            try {
                const response = await fetch(`/api/config/${varName}/reset`, {
                    method: 'POST'
                });

                if (response.ok) successCount++;
            } catch (error) {
                console.error(`Failed to reset ${varName}:`, error);
            }
        }

        if (successCount > 0) {
            this.showSuccess(`Reset ${successCount} setting${successCount !== 1 ? 's' : ''} to defaults`);
            // Reload settings
            await this.loadConfigCategories();
            this.renderTabContent(tabName);
        } else {
            this.showError('Failed to reset settings');
        }
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showInfo(message) {
        this.showToast(message, 'info');
    }

    showToast(message, type = 'info') {
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500'
        };

        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-3 rounded-lg shadow-lg z-50 animate-fadeIn`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('animate-fadeOut');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize settings manager
const settingsManager = new SettingsManager();

// Hook into existing page navigation
if (typeof window.pageNavigationHooks === 'undefined') {
    window.pageNavigationHooks = {};
}

window.pageNavigationHooks.settings = async () => {
    await settingsManager.init();
};

// Also initialize when page loads if settings is shown
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', async () => {
        const settingsPage = document.getElementById('page-settings');
        if (settingsPage && !settingsPage.classList.contains('hidden')) {
            await settingsManager.init();
        }
    });
}
