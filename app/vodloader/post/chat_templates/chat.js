/**
 * Twitch Chat Overlay JavaScript
 * Handles message management, DOM manipulation, and deterministic positioning
 */

class ChatOverlay {
    constructor() {
        this.messages = [];
        this.config = {};
        this.chatContainer = null;
        this.chatMessages = null;
        this.currentTimestamp = 0;
        this.visibleMessages = new Map(); // Track currently visible messages
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }
    
    setup() {
        // Get DOM elements
        this.chatContainer = document.getElementById('chat-container');
        this.chatMessages = document.getElementById('chat-messages');
        
        if (!this.chatContainer || !this.chatMessages) {
            console.error('Required DOM elements not found');
            return;
        }
        
        // Load configuration and data from injected scripts
        this.loadConfiguration();
        this.loadMessages();
        
        // Apply positioning class based on configuration
        this.applyPositioning();
        
        console.log('Chat overlay initialized with', this.messages.length, 'messages');
    }
    
    loadConfiguration() {
        // Configuration will be injected into the chat-config script tag
        const configScript = document.getElementById('chat-config');
        if (configScript && configScript.textContent) {
            try {
                // Extract configuration from script content
                const configMatch = configScript.textContent.match(/window\.chatConfig\s*=\s*({.*?});/s);
                if (configMatch) {
                    this.config = JSON.parse(configMatch[1]);
                }
            } catch (e) {
                console.warn('Failed to parse chat configuration:', e);
                this.config = this.getDefaultConfig();
            }
        } else {
            this.config = this.getDefaultConfig();
        }
    }
    
    loadMessages() {
        // Message data will be injected into the chat-data script tag
        const dataScript = document.getElementById('chat-data');
        if (dataScript && dataScript.textContent) {
            try {
                // Extract messages from script content
                const dataMatch = dataScript.textContent.match(/window\.chatMessages\s*=\s*(\[.*?\]);/s);
                if (dataMatch) {
                    this.messages = JSON.parse(dataMatch[1]);
                    // Sort messages by timestamp to ensure proper ordering
                    this.messages.sort((a, b) => a.timestamp - b.timestamp);
                }
            } catch (e) {
                console.warn('Failed to parse chat messages:', e);
                this.messages = [];
            }
        }
    }
    
    getDefaultConfig() {
        return {
            messageDuration: 30.0,
            overlayWidth: 350,
            overlayHeight: 400,
            position: 'top-right',
            padding: 20
        };
    }
    
    applyPositioning() {
        // Remove any existing position classes
        const positionClasses = ['position-top-left', 'position-top-right', 'position-bottom-left', 
                                'position-bottom-right', 'position-left', 'position-right'];
        positionClasses.forEach(cls => this.chatContainer.classList.remove(cls));
        
        // Apply the configured position class
        const positionClass = `position-${this.config.position || 'top-right'}`;
        this.chatContainer.classList.add(positionClass);
    }
    
    /**
     * Render chat state at a specific timestamp (deterministic)
     * This is the core method for deterministic positioning
     */
    renderAtTimestamp(timestamp) {
        this.currentTimestamp = timestamp;
        
        // Calculate which messages should be visible at this timestamp
        const visibleMessageData = this.getVisibleMessagesAtTimestamp(timestamp);
        
        // Get currently displayed message IDs
        const currentMessageIds = new Set(Array.from(this.visibleMessages.keys()));
        const newMessageIds = new Set(visibleMessageData.map(msg => msg.id));
        
        // Remove messages that should no longer be visible
        for (const messageId of currentMessageIds) {
            if (!newMessageIds.has(messageId)) {
                this.removeMessage(messageId);
            }
        }
        
        // Add new messages that should be visible
        for (const messageData of visibleMessageData) {
            if (!currentMessageIds.has(messageData.id)) {
                this.addMessage(messageData);
            }
        }
        
        // Update positions of all visible messages
        this.updateMessagePositions(visibleMessageData);
    }
    
    /**
     * Calculate which messages should be visible at a given timestamp
     * Returns messages with their calculated positions
     */
    getVisibleMessagesAtTimestamp(timestamp) {
        const messageDuration = this.config.messageDuration || 30.0;
        const visibleMessages = [];
        
        // Find all messages that should be visible at this timestamp
        for (const message of this.messages) {
            const messageStartTime = message.timestamp;
            const messageEndTime = messageStartTime + messageDuration;
            
            // Message is visible if current timestamp is within its display window
            if (timestamp >= messageStartTime && timestamp < messageEndTime) {
                // Calculate how long this message has been visible
                const visibleDuration = timestamp - messageStartTime;
                
                visibleMessages.push({
                    ...message,
                    visibleDuration: visibleDuration,
                    startTime: messageStartTime,
                    endTime: messageEndTime
                });
            }
        }
        
        // Sort by start time to maintain proper stacking order (oldest at top)
        visibleMessages.sort((a, b) => a.startTime - b.startTime);
        
        return visibleMessages;
    }
    
    /**
     * Add a message to the DOM
     */
    addMessage(messageData) {
        const messageElement = this.createMessageElement(messageData);
        
        // Add to the bottom of the chat (new messages appear at bottom)
        this.chatMessages.appendChild(messageElement);
        
        // Track the message
        this.visibleMessages.set(messageData.id, {
            element: messageElement,
            data: messageData
        });
        
        // Trigger enter animation
        requestAnimationFrame(() => {
            messageElement.classList.remove('entering');
            messageElement.classList.add('entered');
        });
    }
    
    /**
     * Remove a message from the DOM
     */
    removeMessage(messageId) {
        const messageInfo = this.visibleMessages.get(messageId);
        if (!messageInfo) return;
        
        const element = messageInfo.element;
        
        // Trigger exit animation
        element.classList.add('exiting');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.visibleMessages.delete(messageId);
        }, 300); // Match CSS transition duration
    }
    
    /**
     * Update positions of all visible messages based on their visibility duration
     */
    updateMessagePositions(visibleMessageData) {
        // Messages are positioned by DOM order (bottom to top)
        // Older messages naturally move up as new ones are added
        // No additional positioning logic needed for basic chat behavior
        
        // Could add advanced positioning logic here if needed for special effects
        // For now, rely on CSS flexbox and natural DOM ordering
    }
    
    /**
     * Create a DOM element for a chat message
     */
    createMessageElement(messageData) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message entering';
        messageDiv.setAttribute('data-message-id', messageData.id);
        
        // Create username element
        const usernameSpan = document.createElement('span');
        usernameSpan.className = 'chat-username';
        usernameSpan.textContent = messageData.username + ':';
        
        // Apply Twitch username color if available
        if (messageData.color) {
            usernameSpan.style.color = messageData.color;
        } else {
            // Use a default color class based on username hash
            const colorClass = this.getUsernameColorClass(messageData.username);
            usernameSpan.classList.add(colorClass);
        }
        
        // Create message text element
        const textSpan = document.createElement('span');
        textSpan.className = 'chat-text';
        textSpan.textContent = ' ' + messageData.text;
        
        // Optional: Add timestamp for debugging
        if (this.config.showTimestamps) {
            const timestampSpan = document.createElement('span');
            timestampSpan.className = 'chat-timestamp';
            timestampSpan.textContent = this.formatTimestamp(messageData.timestamp);
            messageDiv.appendChild(timestampSpan);
        }
        
        messageDiv.appendChild(usernameSpan);
        messageDiv.appendChild(textSpan);
        
        return messageDiv;
    }
    
    /**
     * Get a color class for username based on hash (fallback for missing Twitch colors)
     */
    getUsernameColorClass(username) {
        const colors = ['color-red', 'color-blue', 'color-green', 'color-purple', 
                       'color-orange', 'color-pink', 'color-yellow', 'color-cyan'];
        
        // Simple hash function to consistently assign colors
        let hash = 0;
        for (let i = 0; i < username.length; i++) {
            hash = ((hash << 5) - hash + username.charCodeAt(i)) & 0xffffffff;
        }
        
        return colors[Math.abs(hash) % colors.length];
    }
    
    /**
     * Format timestamp for display
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString();
    }
    
    /**
     * Clear all messages from the chat
     */
    clearMessages() {
        this.chatMessages.innerHTML = '';
        this.visibleMessages.clear();
    }
    
    /**
     * Get the current state of the chat for debugging
     */
    getState() {
        return {
            currentTimestamp: this.currentTimestamp,
            visibleMessageCount: this.visibleMessages.size,
            totalMessages: this.messages.length,
            config: this.config
        };
    }
}

// Global functions that can be called by the browser automation
window.ChatOverlay = ChatOverlay;

// Initialize chat overlay when script loads
let chatOverlay;

// Function to initialize the chat overlay (called by browser automation)
window.initializeChatOverlay = function() {
    chatOverlay = new ChatOverlay();
    return chatOverlay;
};

// Function to render chat at specific timestamp (called by browser automation)
window.renderChatAtTimestamp = function(timestamp) {
    if (!chatOverlay) {
        chatOverlay = new ChatOverlay();
    }
    chatOverlay.renderAtTimestamp(timestamp);
};

// Function to get chat state (for debugging)
window.getChatState = function() {
    return chatOverlay ? chatOverlay.getState() : null;
};

// Auto-initialize if not in automation mode
if (!window.AUTOMATION_MODE) {
    window.addEventListener('load', () => {
        window.initializeChatOverlay();
    });
}