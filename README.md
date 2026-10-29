WasmBox Sandbox — Frontend

Overview

WasmBox Sandbox is a React-based interface for writing Python code, running it, and viewing execution results.

Features

- Python code editor using React and Monaco.
- Run button with execution status and output display.
- Success, error, and timeout status previews.
- Plugin Manager with Save, List, and Load functionality.
- Simulated webhook functionality.
- Friendly error messages and execution-time display.

Requirements

- Node.js and npm.
- Backend running at "http://localhost:8000" for real Python execution.

Installation

Open a terminal in the "frontend" folder and run:

npm install

Start the frontend

npm run dev

Open the local URL displayed in the terminal, usually "http://localhost:5173".

Build the frontend

npm run build

Testing

The test cases are documented in "TEST_SHEET.md".

Important limitations

- Python execution uses the existing backend API.
- Plugin Save, List, and Load and webhook actions currently use temporary mock data in the frontend.
- Demo status previews display example results and do not execute Python.
- Mock plugin data may disappear after refreshing the page.
- Real plugin and webhook integration requires a confirmed backend API contract.

Screenshots

Add screenshots of the following features when available:

- Python execution success.
- Python execution error.
- Plugin Save and Load.
- Webhook demo result.

Only label a screenshot as a real backend result when it has been verified against the backend.

Build status

The frontend build was previously completed successfully. Run "npm run build" again after your latest changes to verify the current version.