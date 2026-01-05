# Jarvis - Personal AI Assistant

A modular, permission-based AI assistant that runs locally and supports voice commands, system control, and future mobile integration. The assistant only responds to commands that start with "Jarvis".

## 🎯 Features

### Voice-Controlled System
- **Speech Recognition**: Converts spoken commands to text using Google's Speech API
- **Text-to-Speech**: Provides audio responses using pyttsx3
- **Command Classification**: Intelligently categorizes user intents
- **Jarvis Activation**: Only responds to commands prefixed with "Jarvis"

### Daily Task Management
- **Add Tasks**: Say "Jarvis add task [description]" to create new tasks
- **Read Tasks**: Say "Jarvis read my tasks" to list all tasks with completion status
- **Complete Tasks**: Say "Jarvis complete task [number]" to mark tasks as done
- **Local Storage**: Tasks stored securely in JSON format on your device

### Safe System Control
- **Permission-Based**: Every system action requires explicit user approval
- **Application Control**: Open Notepad, Calculator, Web Browser
- **Decision Logging**: All permission decisions are logged for transparency

### Information Services
- **Time & Date**: Get current time and date information
- **Permission History**: View past permission decisions

### AI Integration (Optional)
- **ChatGPT Integration**: Generate text, draft messages, summarize tasks
- **Gemini Integration**: Smart suggestions, email drafting, task assistance
- **Secure API Keys**: Keys stored locally, never shared
- **Permission Required**: All AI requests require user approval

### Learning AI Features
- **Smart Task Prioritization**: Learns from completion patterns to prioritize tasks
- **Usage Pattern Recognition**: Analyzes when and how you use different features
- **Proactive Suggestions**: Offers helpful suggestions based on time and patterns
- **Task Categorization**: Automatically categorizes tasks (work, shopping, health, household)
- **Personalized Experience**: Adapts to your preferences and habits
- **Privacy-Focused Learning**: All learning data stored locally, never shared

#### How Jarvis Learns:
1. **Task Completion Patterns**: Learns how long different types of tasks take
2. **Usage Patterns**: Tracks when you use different features
3. **Time-Based Suggestions**: Offers contextually relevant suggestions
4. **Priority Prediction**: Uses keywords and patterns to suggest task importance
5. **Category Recognition**: Automatically groups similar tasks together

## 🏗️ Architecture

```
my_ai_assistant/
├── main.py              # Main Jarvis activation system
├── config.txt           # API keys configuration (create from template)
├── demo_learning.py     # Learning AI demonstration script
├── tasks.json           # Task storage (created automatically)
├── preferences.json     # Learning preferences (created automatically)
├── usage_log.json       # Usage patterns for learning (created automatically)
├── permissions.log      # Permission decision history
├── core/                # Core AI logic
│   ├── brain.py         # Command processing and classification
│   ├── memory.py        # Task storage and learning AI
│   └── permissions.py   # Permission handling system
├── input/               # Input processing
│   ├── voice.py         # Speech recognition with Jarvis filter
│   └── text.py          # Text input (future)
├── output/              # Output systems
│   └── speech.py        # Text-to-speech responses
├── integrations/        # External service integrations
│   ├── chatgpt.py       # OpenAI ChatGPT integration
│   └── gemini.py        # Google Gemini integration
└── mobile/              # Mobile app components
```

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Microphone for voice input
- Internet connection for speech recognition

### Installation
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Configure AI integrations:
   - Copy `config.txt` and add your API keys
   - Or set environment variables: `OPENAI_API_KEY` and `GOOGLE_API_KEY`
4. Run the assistant:
   ```bash
   python main.py
   ```

## 🎤 Voice Commands

**Important**: All commands must start with "Jarvis" to get a response.

### Task Management
- "Jarvis add task buy groceries"
- "Jarvis read my tasks"
- "Jarvis complete task 1"

### System Control
- "Jarvis open notepad"
- "Jarvis open browser"
- "Jarvis open calculator"

### Information
- "Jarvis what time is it"
- "Jarvis what date is it"
- "Jarvis show permission history"

### AI Integration
- "Jarvis ask ChatGPT [question]"
- "Jarvis ask Gemini [question]"
- "Jarvis summarize tasks"
- "Jarvis draft message [topic]"
- "Jarvis suggest task [description]"
- "Jarvis draft email [subject]"

### Learning AI
- "Jarvis give me suggestions" - Get smart suggestions
- "Jarvis update priorities" - Update task priorities based on learning
- "Jarvis analyze patterns" - View usage patterns

### Control
- "Jarvis exit" or "Jarvis quit"

## 🔒 Safety & Privacy

- **Local Execution**: All processing happens on your device
- **Permission Required**: No action performed without user consent
- **No Data Sharing**: No information sent to external servers (except speech recognition)
- **Transparent Logging**: Permission decisions are logged locally

## 🛡️ Ethical Design

This AI assistant follows responsible AI principles:
- Human-in-the-loop for all sensitive actions
- Clear communication of intended actions
- User control and override capabilities
- Privacy-focused data handling

## 📝 Future Enhancements

- Mobile app integration
- Additional voice commands
- Integration with external services (email, calendar)
- Advanced natural language processing
