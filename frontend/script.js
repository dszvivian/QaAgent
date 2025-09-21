document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const optionType = document.getElementById('option').value;
    
    // Create connection status indicator
    const statusIndicator = document.createElement('div');
    statusIndicator.className = 'status-indicator disconnected';
    statusIndicator.textContent = 'Connecting...';
    document.querySelector('header').appendChild(statusIndicator);
    
    // Connect to Socket.IO server
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 20000
    });
    
    // Socket connection events
    socket.on('connect', () => {
        console.log('Connected to server');
        statusIndicator.className = 'status-indicator connected';
        statusIndicator.textContent = 'Connected';
        
        // Join with option type
        socket.emit('join', { option: optionType });
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        statusIndicator.className = 'status-indicator disconnected';
        statusIndicator.textContent = 'Disconnected';
        
        displayMessage('Disconnected from server. Trying to reconnect...', 'bot-message error');
    });
    
    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        statusIndicator.className = 'status-indicator error';
        statusIndicator.textContent = 'Connection error';
    });
    
    // Handle chat responses
    socket.on('chat response', (data) => {
        if (data && data.response) {
            displayMessage(data.response, 'bot-message');
        }
    });
    
    // Show typing indicator
    socket.on('user typing', () => {
        const existingIndicator = document.getElementById('typing-indicator');
        if (!existingIndicator) {
            const typingIndicator = document.createElement('div');
            typingIndicator.id = 'typing-indicator';
            typingIndicator.className = 'typing-indicator';
            typingIndicator.textContent = 'Processing...';
            chatMessages.appendChild(typingIndicator);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    });
    
    // Remove typing indicator
    socket.on('user stop typing', () => {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    });
    
    // Optional: Listen for debug logs if you want to see detailed information
    socket.on('debug_log', (data) => {
        console.log('Debug:', data);
    });
    
    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const userMessage = userInput.value.trim();
        if (!userMessage) return;
        
        // Display user message
        displayMessage(userMessage, 'user-message');
        
        // Send message to server with option type
        socket.emit('chat message', {
            option: optionType,
            query: userMessage
        });
        
        // Clear input field
        userInput.value = '';
    });
    
    // Display messages in the chat
    function displayMessage(message, className) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.textContent = message;
        chatMessages.appendChild(messageElement);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const optionType = document.getElementById('option').value;
    
    // Create connection status indicator
    const statusIndicator = document.createElement('div');
    statusIndicator.className = 'status-indicator disconnected';
    statusIndicator.textContent = 'Connecting...';
    document.querySelector('header').appendChild(statusIndicator);
    
    // Create typing indicator (hidden by default)
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator hidden';
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    chatMessages.appendChild(typingIndicator);
    
    // Connect to Socket.IO server with reconnection options
    const socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 20000
    });
    
    // Socket connection event handlers
    socket.on('connect', () => {
        console.log('Connected to server');
        statusIndicator.className = 'status-indicator connected';
        statusIndicator.textContent = 'Connected';
        
        // Join with option type
        socket.emit('join', { option: optionType });
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        statusIndicator.className = 'status-indicator disconnected';
        statusIndicator.textContent = 'Disconnected';
    });
    
    socket.on('connect_error', (error) => {
        console.log('Connection error:', error);
        statusIndicator.className = 'status-indicator error';
        statusIndicator.textContent = 'Connection Error';
    });
    
    // Handle incoming chat responses
    socket.on('chat response', (data) => {
        if (data && data.response) {
            displayMessage(data.response, 'bot-message');
        }
    });
    
    // Handle typing indicators
    socket.on('user typing', () => {
        typingIndicator.classList.remove('hidden');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
    
    socket.on('user stop typing', () => {
        typingIndicator.classList.add('hidden');
    });
    
    // Form submission handler
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const userMessage = userInput.value.trim();
        if (!userMessage) return;
        
        // Display user message
        displayMessage(userMessage, 'user-message');
        
        // Send message to server with option type
        socket.emit('chat message', {
            option: optionType,
            query: userMessage
        });
        
        // Clear input field
        userInput.value = '';
    });
    
    // Display messages in the chat
    function displayMessage(message, className) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.textContent = message;
        
        // Insert before the typing indicator
        chatMessages.insertBefore(messageElement, typingIndicator);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});