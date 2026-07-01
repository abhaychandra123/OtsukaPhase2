#!/bin/bash

# Quick-start script for Graph RAG Visualization
# Usage: ./tools/run_visualization.sh

set -e

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$PROJECT_ROOT"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Graph RAG Visualization - Quick Start                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✓ Starting FastAPI Visualization Server..."
echo "  WebSocket: ws://localhost:8001/ws/visualization"
echo "  History: http://localhost:8001/api/visualization/history"
echo ""

# Check if uvicorn is installed, if not try to install it
if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "⚠️  Installing uvicorn..."
    python3 -m pip install uvicorn -q
fi

echo "📊 Dashboard: Open tools/graph_viz_dashboard.html in your browser"
echo "   Or run: python3 -m http.server 8000"
echo "   Then visit: http://localhost:8000/tools/graph_viz_dashboard.html"
echo ""
echo "💡 Try these in Python to emit events:"
echo "   from senpai.graph.query_instrumented import *"
echo "   reps_who_win_viz(category='サーバー')"
echo "   account_graph_viz('C28')"
echo "   connections_viz('C28', 'SRV20')"
echo "   similar_by_graph_viz('D005')"
echo ""
echo "Press Ctrl+C to stop the server"
echo "─────────────────────────────────────────────────────────────"
echo ""

python3 -m uvicorn senpai.api.visualization_server:app \
    --host 0.0.0.0 \
    --port 8001 \
    --reload
