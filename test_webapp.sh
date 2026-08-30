#!/bin/bash
# JARVIS Web UI Test Script

echo "=== JARVIS Web UI Test ==="
echo ""

# Check if server is running
if curl -s --max-time 3 http://127.0.0.1:3000/health > /dev/null 2>&1; then
    echo "✓ Server is running"
else
    echo "✗ Server is not running"
    echo "  Start with: cd /home/shanu/Desktop/Jarvis && python3 run.py"
    exit 1
fi

# Test endpoints
echo ""
echo "Testing endpoints..."

# Health
HEALTH=$(curl -s http://127.0.0.1:3000/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✓ /health - OK"
else
    echo "✗ /health - FAILED"
fi

# Status
STATUS=$(curl -s http://127.0.0.1:3000/status)
if echo "$STATUS" | grep -q "world_state"; then
    echo "✓ /status - OK"
else
    echo "✗ /status - FAILED"
fi

# Web UI
HTML=$(curl -s http://127.0.0.1:3000/)
if echo "$HTML" | grep -q "JARVIS"; then
    echo "✓ / (Web UI) - OK"
else
    echo "✗ / (Web UI) - FAILED"
fi

# CSS
CSS=$(curl -s http://127.0.0.1:3000/css/style.css)
if echo "$CSS" | grep -q "background"; then
    echo "✓ /css/style.css - OK"
else
    echo "✗ /css/style.css - FAILED"
fi

# JS
JS=$(curl -s http://127.0.0.1:3000/js/app.js)
if echo "$JS" | grep -q "JarvisUI"; then
    echo "✓ /js/app.js - OK"
else
    echo "✗ /js/app.js - FAILED"
fi

# Chat
CHAT=$(curl -s -X POST http://127.0.0.1:3000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "hello"}')
if echo "$CHAT" | grep -q "response"; then
    echo "✓ /chat - OK"
else
    echo "✗ /chat - FAILED"
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "Open http://127.0.0.1:3000 in your browser to use JARVIS Web UI"
