#!/bin/bash
# Run the backend with forecast debugging enabled.
# Debug logs appear in this terminal when you trigger a forecast (Forecasting tab or API).
cd "$(dirname "$0")"
echo "Starting Orbital backend (forecast debug logs will appear below)..."
echo ""
echo "Trigger a forecast from the app's Forecasting tab, or:"
echo '  curl -X POST http://localhost:8000/v1/projects/YOUR_PROJECT_ID/forecast \'
echo '    -H "Content-Type: application/json" -d '\''{"horizon": 4}'\'''
echo ""
echo "---"
exec uvicorn main:app
