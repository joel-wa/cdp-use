// Configuration
const API_BASE_URL = 'http://localhost:8000';
const REFRESH_INTERVAL = 2000; // 2 seconds

// State
let workflows = [];
let activeExecutions = [];
let selectedWorkflow = null;
let selectedExecution = null;
let refreshTimer = null;

// DOM Elements
const workflowList = document.getElementById('workflowList');
const workflowInput = document.getElementById('workflowInput');
const workflowDatalist = document.getElementById('workflowDatalist');
const executeForm = document.getElementById('executeForm');
const workflowParams = document.getElementById('workflowParams');
const activeExecutionsContainer = document.getElementById('activeExecutions');
const detailsPanel = document.getElementById('detailsPanel');
const connectionStatus = document.getElementById('connectionStatus');
const connectionText = document.getElementById('connectionText');
const queuedCount = document.getElementById('queuedCount');
const runningCount = document.getElementById('runningCount');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkHealth();
    loadWorkflows();
    startAutoRefresh();
});

// Event Listeners
function setupEventListeners() {
    executeForm.addEventListener('submit', handleExecuteWorkflow);
    document.getElementById('refreshWorkflows').addEventListener('click', loadWorkflows);
    document.getElementById('clearDetails').addEventListener('click', clearDetails);
    
    // Update parameters when workflow input changes
    workflowInput.addEventListener('input', (e) => {
        const workflow = workflows.find(w => w.name === e.target.value);
        if (workflow && workflow.parameters) {
            updateParameterTemplate(workflow);
        }
    });
    
    // Also handle blur to catch datalist selection
    workflowInput.addEventListener('blur', (e) => {
        const workflow = workflows.find(w => w.name === e.target.value);
        if (workflow && workflow.parameters) {
            updateParameterTemplate(workflow);
        }
    });
}

// API Calls
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.detail || 'API request failed');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        showToast(error.message, 'error');
        throw error;
    }
}

async function checkHealth() {
    try {
        const health = await apiCall('/health');
        updateConnectionStatus(true);
        updateSystemStats(health);
    } catch (error) {
        updateConnectionStatus(false);
    }
}

async function loadWorkflows() {
    try {
        const response = await apiCall('/workflows/list');
        workflows = response.workflows;
        renderWorkflowList();
        updateWorkflowSelect();
    } catch (error) {
        workflowList.innerHTML = '<div class="empty-state">Failed to load workflows</div>';
    }
}

async function executeWorkflow(workflowName, parameters, priority, timeout) {
    const payload = {
        workflow_name: workflowName,
        parameters: parameters,
        priority: priority,
        timeout: timeout
    };
    
    const response = await apiCall('/workflows/execute', {
        method: 'POST',
        body: JSON.stringify(payload)
    });
    
    showToast(`Workflow "${workflowName}" submitted successfully`, 'success');
    return response;
}

async function getExecutionStatus(executionId) {
    return await apiCall(`/workflows/status/${executionId}`);
}

async function getExecutionResult(executionId) {
    return await apiCall(`/workflows/result/${executionId}`);
}

async function cancelExecution(executionId) {
    await apiCall(`/workflows/cancel/${executionId}`, {
        method: 'DELETE'
    });
    showToast('Execution cancelled', 'warning');
}

async function loadActiveExecutions() {
    try {
        const response = await apiCall('/workflows/active');
        activeExecutions = response.executions;
        
        // Update counts
        queuedCount.textContent = response.queued;
        runningCount.textContent = response.running;
        
        renderActiveExecutions();
        
        // Update selected execution if it's still active
        if (selectedExecution) {
            const updated = activeExecutions.find(e => e.execution_id === selectedExecution.execution_id);
            if (updated) {
                showExecutionDetails(updated.execution_id);
            } else if (selectedExecution.status !== 'completed' && selectedExecution.status !== 'failed') {
                // Execution completed, fetch final result
                showExecutionDetails(selectedExecution.execution_id);
            }
        }
    } catch (error) {
        console.error('Failed to load active executions:', error);
    }
}

// Rendering Functions
function renderWorkflowList() {
    if (workflows.length === 0) {
        workflowList.innerHTML = '<div class="empty-state">No workflows available</div>';
        return;
    }
    
    workflowList.innerHTML = workflows.map(workflow => `
        <div class="workflow-item" data-workflow="${workflow.name}">
            <div class="workflow-name">${workflow.name}</div>
            <div class="workflow-description">${workflow.description || 'No description'}</div>
            ${workflow.tags && workflow.tags.length > 0 ? `
                <div class="workflow-tags">
                    ${workflow.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                </div>
            ` : ''}
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.workflow-item').forEach(item => {
        item.addEventListener('click', () => {
            const workflowName = item.dataset.workflow;
            selectWorkflow(workflowName);
        });
    });
}

function updateWorkflowSelect() {
    workflowDatalist.innerHTML = workflows.map(w => 
        `<option value="${w.name}">${w.description || w.name}</option>`
    ).join('');
}

function selectWorkflow(workflowName) {
    selectedWorkflow = workflows.find(w => w.name === workflowName);
    
    // Update UI
    document.querySelectorAll('.workflow-item').forEach(item => {
        item.classList.toggle('selected', item.dataset.workflow === workflowName);
    });
    
    workflowInput.value = workflowName;
    updateParameterTemplate(selectedWorkflow);
}

function updateParameterTemplate(workflow) {
    if (!workflow.parameters || workflow.parameters.length === 0) {
        workflowParams.value = '{}';
        return;
    }
    
    const template = {};
    workflow.parameters.forEach(param => {
        template[param] = '';
    });
    
    workflowParams.value = JSON.stringify(template, null, 2);
}

function renderActiveExecutions() {
    if (activeExecutions.length === 0) {
        activeExecutionsContainer.innerHTML = '<div class="empty-state">No active executions</div>';
        return;
    }
    
    activeExecutionsContainer.innerHTML = activeExecutions.map(execution => {
        const elapsed = execution.elapsed_seconds || 0;
        const progress = execution.progress;
        
        return `
            <div class="execution-card" data-execution="${execution.execution_id}">
                <div class="execution-header">
                    <span class="execution-id">${execution.execution_id}</span>
                    <span class="execution-status status-${execution.status}">${execution.status}</span>
                </div>
                <div class="execution-workflow">${execution.workflow_name}</div>
                <div class="execution-time">${formatDuration(elapsed)}</div>
                ${progress ? `
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress.percent_complete}%"></div>
                    </div>
                    <div class="execution-time">
                        Step ${progress.current_step}/${progress.total_steps}: ${progress.step_name}
                    </div>
                ` : ''}
                <div class="execution-actions">
                    <button class="btn btn-secondary btn-small view-details" data-id="${execution.execution_id}">
                        View Details
                    </button>
                    ${execution.status === 'running' || execution.status === 'queued' ? `
                        <button class="btn btn-danger btn-small cancel-execution" data-id="${execution.execution_id}">
                            Cancel
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // Add click handlers
    document.querySelectorAll('.view-details').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            showExecutionDetails(btn.dataset.id);
        });
    });
    
    document.querySelectorAll('.cancel-execution').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm('Are you sure you want to cancel this execution?')) {
                await cancelExecution(btn.dataset.id);
                loadActiveExecutions();
            }
        });
    });
}

async function showExecutionDetails(executionId) {
    try {
        // Try to get full result first
        let execution;
        try {
            execution = await getExecutionResult(executionId);
        } catch {
            // Fall back to status if result not available
            execution = await getExecutionStatus(executionId);
        }
        
        selectedExecution = execution;
        renderExecutionDetails(execution);
    } catch (error) {
        detailsPanel.innerHTML = '<div class="empty-state">Failed to load execution details</div>';
    }
}

function renderExecutionDetails(execution) {
    const isComplete = ['completed', 'failed', 'cancelled', 'timeout'].includes(execution.status);
    
    detailsPanel.innerHTML = `
        <div class="detail-section">
            <h3>Execution Information</h3>
            <div class="detail-grid">
                <div class="detail-row">
                    <span class="detail-label">Execution ID:</span>
                    <span class="detail-value">${execution.execution_id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Workflow:</span>
                    <span class="detail-value">${execution.workflow_name}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value">
                        <span class="execution-status status-${execution.status}">${execution.status}</span>
                    </span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Submitted:</span>
                    <span class="detail-value">${formatTimestamp(execution.submitted_at)}</span>
                </div>
                ${execution.started_at ? `
                    <div class="detail-row">
                        <span class="detail-label">Started:</span>
                        <span class="detail-value">${formatTimestamp(execution.started_at)}</span>
                    </div>
                ` : ''}
                ${execution.completed_at ? `
                    <div class="detail-row">
                        <span class="detail-label">Completed:</span>
                        <span class="detail-value">${formatTimestamp(execution.completed_at)}</span>
                    </div>
                ` : ''}
                ${execution.execution_time ? `
                    <div class="detail-row">
                        <span class="detail-label">Duration:</span>
                        <span class="detail-value">${formatDuration(execution.execution_time)}</span>
                    </div>
                ` : ''}
                ${execution.elapsed_seconds ? `
                    <div class="detail-row">
                        <span class="detail-label">Elapsed:</span>
                        <span class="detail-value">${formatDuration(execution.elapsed_seconds)}</span>
                    </div>
                ` : ''}
            </div>
        </div>
        
        ${execution.progress ? `
            <div class="detail-section">
                <h3>Progress</h3>
                <div class="detail-grid">
                    <div class="detail-row">
                        <span class="detail-label">Step:</span>
                        <span class="detail-value">${execution.progress.current_step} / ${execution.progress.total_steps}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Current Step:</span>
                        <span class="detail-value">${execution.progress.step_name}</span>
                    </div>
                    ${execution.progress.step_tool ? `
                        <div class="detail-row">
                            <span class="detail-label">Tool:</span>
                            <span class="detail-value">${execution.progress.step_tool}</span>
                        </div>
                    ` : ''}
                    <div class="detail-row">
                        <span class="detail-label">Complete:</span>
                        <span class="detail-value">${execution.progress.percent_complete}%</span>
                    </div>
                </div>
                <div class="progress-bar" style="margin-top: 1rem; height: 4px;">
                    <div class="progress-fill" style="width: ${execution.progress.percent_complete}%"></div>
                </div>
            </div>
        ` : ''}
        
        ${execution.result ? `
            <div class="detail-section">
                <h3>Result</h3>
                <div class="code-block">${JSON.stringify(execution.result, null, 2)}</div>
            </div>
        ` : ''}
        
        ${execution.outputs ? `
            <div class="detail-section">
                <h3>Outputs</h3>
                <div class="code-block">${JSON.stringify(execution.outputs, null, 2)}</div>
            </div>
        ` : ''}
        
        ${execution.error ? `
            <div class="detail-section">
                <h3>Error</h3>
                <div class="code-block" style="color: #ff6b6b;">${execution.error}</div>
                ${execution.error_step ? `
                    <div class="detail-row" style="margin-top: 0.5rem;">
                        <span class="detail-label">Error Step:</span>
                        <span class="detail-value">${execution.error_step}</span>
                    </div>
                ` : ''}
            </div>
        ` : ''}
        
        ${isComplete && execution.status !== 'failed' ? `
            <button class="btn btn-secondary" onclick="copyToClipboard('${execution.execution_id}')">
                Copy Execution ID
            </button>
        ` : ''}
    `;
}

function clearDetails() {
    selectedExecution = null;
    detailsPanel.innerHTML = '<div class="empty-state">Select an execution to view details</div>';
}

function updateConnectionStatus(connected) {
    connectionStatus.classList.toggle('connected', connected);
    connectionText.textContent = connected ? 'Connected' : 'Disconnected';
}

function updateSystemStats(health) {
    document.getElementById('uptime').textContent = formatDuration(health.uptime_seconds);
    document.getElementById('activeSessions').textContent = health.session_pool.active || 0;
    document.getElementById('availableSessions').textContent = health.session_pool.available || 0;
    document.getElementById('totalExecutions').textContent = health.active_executions || 0;
}

// Form Handlers
async function handleExecuteWorkflow(e) {
    e.preventDefault();
    
    const workflowName = workflowInput.value.trim();
    if (!workflowName) {
        showToast('Please enter a workflow name', 'warning');
        return;
    }
    
    // Validate workflow exists
    const workflow = workflows.find(w => w.name === workflowName);
    if (!workflow) {
        showToast(`Workflow "${workflowName}" not found`, 'error');
        return;
    }
    
    let parameters = {};
    try {
        parameters = JSON.parse(workflowParams.value);
    } catch (error) {
        showToast('Invalid JSON in parameters', 'error');
        return;
    }
    
    const priority = document.getElementById('priority').value;
    const timeout = parseInt(document.getElementById('timeout').value);
    
    try {
        const response = await executeWorkflow(workflowName, parameters, priority, timeout);
        
        // Reload active executions
        await loadActiveExecutions();
        
        // Show the new execution details
        showExecutionDetails(response.execution_id);
    } catch (error) {
        // Error already shown by apiCall
    }
}

// Auto-refresh
function startAutoRefresh() {
    refreshTimer = setInterval(() => {
        checkHealth();
        loadActiveExecutions();
    }, REFRESH_INTERVAL);
}

// Utility Functions
function formatTimestamp(timestamp) {
    if (!timestamp) return '--';
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function formatDuration(seconds) {
    if (!seconds) return '0s';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    parts.push(`${secs}s`);
    
    return parts.join(' ');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    const container = document.getElementById('toastContainer');
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard', 'success');
    });
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
});
