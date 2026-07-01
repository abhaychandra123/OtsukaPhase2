# 🎬 Graph RAG Visualization - Quick Start

You now have a **real-time visualization system** to see your Graph RAG in action and demonstrate its advantages over traditional approaches.

## What You Got

### 1. **Real-Time Event Streaming** (`senpai/graph/visualization.py`)
- `QueryTracer`: Instruments query execution to emit events
- `VisualizationHub`: Broadcasts events to all connected clients
- LLM context window estimation (tokens, cost, efficiency)

### 2. **Instrumented Query Functions** (`senpai/graph/query_instrumented.py`)
Drop-in replacements for your base queries that emit visualization events:
- `reps_who_win_viz()` - Find winning reps by category/industry
- `account_graph_viz()` - Customer relationship neighborhood
- `connections_viz()` - Shortest relational path between entities
- `similar_by_graph_viz()` - Graph-based deal similarity

### 3. **FastAPI WebSocket Server** (`senpai/api/visualization_server.py`)
Lightweight server that broadcasts query execution events:
- **WebSocket**: `ws://localhost:8001/ws/visualization` - Real-time events
- **HTTP**: `GET /api/visualization/history` - Event replay
- **HTTP**: `POST /api/visualization/clear-history` - Reset state

### 4. **Interactive Dashboard** (`tools/graph_viz_dashboard.html`)
Standalone HTML dashboard (no build step needed!) showing:
- **Graph Visualization**: Force-directed layout of node traversal
- **Execution Steps**: Step-by-step breakdown of query execution
- **LLM Context**: Token counts, cost estimates, efficiency metrics
- **Performance Comparison**: Graph RAG vs Traditional side-by-side

### 5. **Demo & Benchmark Scripts** (`demo_visualization.py`)
```bash
python demo_visualization.py --demo         # Full interactive demo
python demo_visualization.py --benchmark    # Performance comparison
python demo_visualization.py --architecture # Show system diagram
```

## 🚀 Getting Started (3 Steps)

### Step 1: Start the Visualization Server

```bash
# Option A: Using the provided script
./tools/run_visualization.sh

# Option B: Manual startup
python3 -m uvicorn senpai.api.visualization_server:app --host 0.0.0.0 --port 8001
```

You should see:
```
Uvicorn running on http://0.0.0.0:8001
Press CTRL+C to quit
```

### Step 2: Open the Dashboard

Open `tools/graph_viz_dashboard.html` in your browser:

```bash
# If you want to serve it:
cd tools && python3 -m http.server 8000
# Then visit: http://localhost:8000/graph_viz_dashboard.html

# Or just open directly:
open tools/graph_viz_dashboard.html  # macOS
xdg-open tools/graph_viz_dashboard.html  # Linux
```

You should see the dashboard with a status "🟢 Connected" at the top.

### Step 3: Run Queries

In Python (REPL, Jupyter, or script), run instrumented queries:

```python
from senpai.graph.query_instrumented import *

# These automatically emit visualization events
result = reps_who_win_viz(category="サーバー")
result = account_graph_viz("C28")
result = connections_viz("C28", "SRV20")
result = similar_by_graph_viz("D005", limit=5)
```

**Watch the dashboard update in real-time** with:
- ✓ Nodes being visited (light up in blue)
- ✓ Edges being traversed
- ✓ Context chunks prepared for LLM
- ✓ Performance metrics updating
- ✓ Comparison with traditional approach

## 📊 What You'll See

### Graph Visualization
Shows the actual subgraph traversed:
```
   Rep (matched)
      ↓
  Deal (matched)
      ↓
  Customer (matched)
      ↓
  Product
```

Blue circles = filtered/matched nodes | Gray circles = visited but not matched

### Execution Metrics
```
Step 1: Building graph (30 nodes, 45 edges, 12.3ms)
Step 2: Filtering (125 nodes, 156 edges, 18.5ms)
Step 3: Aggregating (8 nodes, 12 edges, 5.2ms)
```

### LLM Context
```
LLM Tokens: 2,450
Context Chunks: 12
Estimated Cost: $0.0037
Efficiency: 4.0x smaller than naive approach
```

### Performance Comparison
```
Graph RAG:  36ms | 2,450 tokens | 95% quality
Traditional: 90ms | 9,800 tokens | 65% quality
───────────────────────────────────────────
🚀 2.5x faster | 4.0x fewer tokens | 46% better quality
```

## 💡 Use Cases

### 1. **Live Demo to Stakeholders**
```
1. Open dashboard in browser
2. Run queries from your laptop
3. Point at the metrics while explaining:
   "See how the graph gets traversed step-by-step?"
   "4x fewer tokens sent to the LLM compared to full-text search"
   "All GPU-free and deterministic - no black boxes"
```

### 2. **Performance Benchmarking**
```bash
python demo_visualization.py --benchmark
# Outputs real latency, token counts, quality estimates
```

### 3. **Debugging Query Issues**
```python
from senpai.graph.query_instrumented import *

# Watch what nodes get visited
# See if filtering logic is correct
# Verify context window composition
result = account_graph_viz("C28")
```

### 4. **Integrate with Your Own Queries**
```python
from senpai.graph.visualization import create_query_tracer

def my_custom_query():
    tracer = create_query_tracer("my_query", {"param": "value"})
    
    tracer.start_step(1, "My first step")
    tracer.visit_node("E123", "entity", "Entity Label", depth=0, matched=True)
    tracer.traverse_edge("E123", "E456", "RELATED_TO")
    tracer.end_step()
    
    tracer.finalize()  # Emits all events
```

## 📁 File Structure

```
OtsukaPhase2/
├── senpai/
│   ├── graph/
│   │   ├── visualization.py           # Core instrumentation
│   │   ├── query_instrumented.py      # Wrapped query functions
│   │   ├── build.py                   # (existing) Graph building
│   │   └── query.py                   # (existing) Base queries
│   └── api/
│       ├── visualization_server.py    # WebSocket server
│       └── server.py                  # (existing) Main API
├── tools/
│   ├── graph_viz_dashboard.html       # 🎯 Open this in browser
│   ├── run_visualization.sh           # Easy startup script
│   ├── VISUALIZATION_README.md        # Full documentation
│   └── ...
└── demo_visualization.py              # Demo scripts
```

## 🎯 Key Insights to Demonstrate

When showing this to stakeholders, highlight:

1. **Deterministic & Fast**: Graph queries are O(n) scans - no ML/AI needed, runs instantly
2. **Token Efficient**: Only relevant entities sent to LLM - no full-text search noise
3. **Explainable**: Every step shown - no black box embeddings or semantic search
4. **Cost Reduction**: 4x fewer tokens = 75% cheaper LLM calls
5. **Quality**: Structured data beats keyword matching for relationship queries

## 🔧 Customization

### Change Server Port
```bash
python3 -m uvicorn senpai.api.visualization_server:app --port 9999
```

Then update `tools/graph_viz_dashboard.html`:
```javascript
const config = {
    wsUrl: `ws://${window.location.hostname}:9999/ws/visualization`,
};
```

### Modify Dashboard Styling
Edit `tools/graph_viz_dashboard.html` - it's vanilla HTML/CSS/JS with no build:
```html
<!-- Change colors, layout, add new metrics, etc -->
<!-- Just save and refresh browser -->
```

### Add More Metrics
In `senpai/graph/visualization.py`, add to `QueryExecutionTrace`:
```python
@dataclass
class QueryExecutionTrace:
    # ... existing fields ...
    custom_metric: float = 0.0  # Add your metric
```

## ❓ Troubleshooting

### Dashboard shows "Disconnected"
```bash
# Check server is running
lsof -i :8001

# If not, start it:
./tools/run_visualization.sh

# Restart server and refresh browser
```

### No events appearing
```python
# Make sure you're using *_viz functions, not base functions
from senpai.graph.query_instrumented import reps_who_win_viz  # ✓ Correct
from senpai.graph.query import reps_who_win  # ✗ Wrong - no events
```

### WebSocket connection error
- Check firewall allows port 8001
- Browser may need HTTPS for production (use wss:// protocol)
- Check browser console for errors (F12 → Console tab)

## 📚 More Info

- **Full Documentation**: `tools/VISUALIZATION_README.md`
- **Architecture Diagram**: `python demo_visualization.py --architecture`
- **API Reference**: Check docstrings in `senpai/graph/visualization.py`

## 🎓 Next Steps

1. ✅ Start the server: `./tools/run_visualization.sh`
2. ✅ Open dashboard: Open `tools/graph_viz_dashboard.html` in browser
3. ✅ Run a query: `python3 -c "from senpai.graph.query_instrumented import *; reps_who_win_viz(category='サーバー')"`
4. ✅ Watch the dashboard light up!
5. 🎬 Record a demo or show live to stakeholders
6. 📊 Use metrics to guide feature development

---

**That's it!** You now have a real-time window into your Graph RAG processing. Enjoy! 🚀
