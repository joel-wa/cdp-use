document.addEventListener('DOMContentLoaded', () => {
    // State
    let socket = null;
    let isConnected = false;
    let isRecording = false;

    // DOM Elements
    const connectionStatus = document.getElementById('connection-status');
    const connectionText = document.getElementById('connection-text');
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const toggleRecordingBtn = document.getElementById('toggle-recording-btn');
    const recordingIndicator = document.getElementById('recording-indicator');
    const navItems = document.querySelectorAll('.nav-item');
    const viewPanels = document.querySelectorAll('.view-panel');
    const workflowList = document.getElementById('workflow-list');
    const refreshWorkflowsBtn = document.getElementById('refresh-workflows');

    // Initialize WebSocket
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            isConnected = true;
            updateConnectionStatus(true);
            console.log('Connected to WebSocket');
        };

        socket.onclose = () => {
            isConnected = false;
            updateConnectionStatus(false);
            console.log('Disconnected from WebSocket');
            // Try to reconnect after 3 seconds
            setTimeout(connectWebSocket, 3000);
        };

        socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleServerMessage(message);
        };
    }

    function updateConnectionStatus(connected) {
        if (connected) {
            connectionStatus.classList.add('connected');
            connectionText.textContent = 'Connected';
        } else {
            connectionStatus.classList.remove('connected');
            connectionText.textContent = 'Disconnected';
        }
    }

    function handleServerMessage(message) {
        switch (message.type) {
            case 'assistant_response':
                addMessage('assistant', message.content);
                break;
            case 'status':
                // Handle status updates (e.g., show typing indicator)
                break;
            case 'recording_status':
                updateRecordingState(message.is_recording);
                break;
            case 'error':
                addMessage('system', `Error: ${message.content}`);
                break;
        }
    }

    // Chat Functions
    function addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        
        // Simple markdown-like parsing for code blocks could go here
        contentDiv.innerHTML = `<p>${content.replace(/\n/g, '<br>')}</p>`;
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage() {
        const text = userInput.value.trim();
        if (!text || !isConnected) return;

        addMessage('user', text);
        socket.send(JSON.stringify({
            type: 'user_input',
            content: text
        }));

        userInput.value = '';
    }

    // Recording Functions
    function updateRecordingState(recording) {
        isRecording = recording;
        if (isRecording) {
            toggleRecordingBtn.innerHTML = '<span class="record-icon">■</span> Stop Recording';
            toggleRecordingBtn.classList.add('recording');
            recordingIndicator.classList.remove('hidden');
        } else {
            toggleRecordingBtn.innerHTML = '<span class="record-icon">●</span> Start Recording';
            toggleRecordingBtn.classList.remove('recording');
            recordingIndicator.classList.add('hidden');
        }
    }

    // Workflow Library Functions
    async function loadWorkflows() {
        try {
            workflowList.innerHTML = '<div class="loading-state">Loading workflows...</div>';
            const response = await fetch('/api/workflows');
            const data = await response.json();
            
            renderWorkflows(data.workflows);
        } catch (error) {
            console.error('Error loading workflows:', error);
            workflowList.innerHTML = '<div class="error-state">Failed to load workflows</div>';
        }
    }

    function renderWorkflows(workflows) {
        if (!workflows || workflows.length === 0) {
            workflowList.innerHTML = '<div class="empty-state">No workflows found</div>';
            return;
        }

        workflowList.innerHTML = workflows.map(name => `
            <div class="workflow-card" onclick="alert('Workflow details for: ${name}')">
                <h3>${name}</h3>
                <p>Click to view details</p>
                <div class="workflow-meta">
                    <span>Workflow</span>
                </div>
            </div>
        `).join('');
    }

    // Event Listeners
    sendBtn.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    toggleRecordingBtn.addEventListener('click', () => {
        if (!isConnected) return;
        
        // Send command to toggle recording via chat for now
        // In a real implementation, we'd have a dedicated endpoint or message type
        const command = isRecording ? "stop recording" : "start recording";
        socket.send(JSON.stringify({
            type: 'user_input',
            content: command
        }));
    });

    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Update nav active state
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Switch views
            const viewId = item.dataset.view;
            viewPanels.forEach(panel => panel.classList.remove('active'));
            document.getElementById(viewId).classList.add('active');

            // Load data if needed
            if (viewId === 'library-view') {
                loadWorkflows();
            }
        });
    });

    refreshWorkflowsBtn.addEventListener('click', loadWorkflows);

    // Initial connection
    connectWebSocket();
});