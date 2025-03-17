
        // DOM elements
        const chatContainer = document.getElementById('chatContainer');
        const emptyState = document.getElementById('emptyState');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const chatHistory = document.getElementById('chatHistory');
        const examplePrompts = document.querySelectorAll('.example-prompt');
        const mobileMenuButton = document.querySelector('.mobile-menu-button');
        const sidebar = document.querySelector('.sidebar');
        
        // Chat state
        let messages = [];
        let chats = [];
        let currentChatId = null;
        
        // Event listeners
        messageInput.addEventListener('input', function() {
            sendButton.disabled = messageInput.value.trim() === '';
            
            // Auto-resize textarea
            messageInput.style.height = 'auto';
            messageInput.style.height = (messageInput.scrollHeight) + 'px';
        });
        
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendButton.disabled) {
                    sendMessage();
                }
            }
        });
        
        sendButton.addEventListener('click', sendMessage);
        
        document.querySelector('.new-chat').addEventListener('click', createNewChat);
        
        // Mobile menu toggle
        mobileMenuButton.addEventListener('click', function() {
            sidebar.style.display = sidebar.style.display === 'none' || 
                                   sidebar.style.display === '' ? 'flex' : 'none';
        });
        
        // Set up example prompts
        examplePrompts.forEach(prompt => {
            prompt.addEventListener('click', function() {
                const promptText = this.querySelector('.example-prompt-text').textContent;
                messageInput.value = promptText;
                messageInput.dispatchEvent(new Event('input'));
                sendMessage();
            });
        });
        
        // Functions
        function sendMessage() {
            const messageText = messageInput.value.trim();
            if (!messageText) return;
            
            // Create chat if none exists
            if (!currentChatId) {
                createNewChat();
            }
            
            // Hide empty state
            emptyState.style.display = 'none';
            
            // Add user message to UI
            addMessageToUI(messageText, 'user');
            
            // Add to messages array
            messages.push({
                role: 'user',
                content: messageText
            });
            
            // Clear input
            messageInput.value = '';
            messageInput.style.height = 'auto';
            sendButton.disabled = true;
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
            
            // Simulate AI response (in a real app, you'd call an API here)
            simulateResponse(messageText);
            
            // Update chat title in sidebar
            updateChatTitle(messageText);
        }
        
        function addMessageToUI(text, role) {
            const wrapperDiv = document.createElement('div');
            wrapperDiv.className = `message-wrapper ${role}`;
        }