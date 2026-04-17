#!/usr/bin/env python3
"""
Live Trading Dashboard
A simple web interface to monitor the multi-symbol trading bot.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import ccxt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_config
from utils.logger import get_logger
from multi_symbol_config import MultiSymbolConfig

app = FastAPI(title="Live Trading Dashboard")
logger = get_logger("Dashboard")

# Global state
trading_data = {
    "status": "initializing",
    "balance": {},
    "positions": [],
    "symbols": MultiSymbolConfig.get_active_symbols(),
    "last_update": datetime.now().isoformat(),
    "performance": {}
}

class TradingMonitor:
    """Monitor trading bot performance and account status."""
    
    def __init__(self):
        self.config = get_config()
        self.exchange = None
        self.initial_balance = None
        
    async def initialize(self):
        """Initialize exchange connection."""
        try:
            exchange_config = self.config.to_ccxt_config(sandbox=False)
            self.exchange = ccxt.bybit(exchange_config)
            self.exchange.load_markets()
            
            # Get initial balance
            balance = self.exchange.fetch_balance()
            self.initial_balance = balance.get('USDT', {}).get('total', 0)
            
            logger.info("Trading monitor initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize monitor: {e}")
            return False
    
    async def update_data(self):
        """Update trading data."""
        global trading_data
        
        try:
            if not self.exchange:
                await self.initialize()
                
            # Fetch current balance
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            
            # Fetch positions
            positions = self.exchange.fetch_positions()
            open_positions = [
                {
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "size": pos['contracts'],
                    "entry_price": pos['entryPrice'],
                    "mark_price": pos['markPrice'],
                    "pnl": pos['unrealizedPnl'],
                    "pnl_percentage": pos['percentage']
                }
                for pos in positions if pos['contracts'] > 0
            ]
            
            # Calculate performance
            current_balance = usdt_balance.get('total', 0)
            if self.initial_balance:
                total_pnl = current_balance - self.initial_balance
                total_pnl_pct = (total_pnl / self.initial_balance) * 100
            else:
                total_pnl = 0
                total_pnl_pct = 0
            
            # Update global data
            trading_data.update({
                "status": "running",
                "balance": {
                    "free": usdt_balance.get('free', 0),
                    "used": usdt_balance.get('used', 0),
                    "total": current_balance
                },
                "positions": open_positions,
                "last_update": datetime.now().isoformat(),
                "performance": {
                    "initial_balance": self.initial_balance,
                    "current_balance": current_balance,
                    "total_pnl": total_pnl,
                    "total_pnl_pct": total_pnl_pct,
                    "open_positions": len(open_positions)
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            trading_data["status"] = f"error: {e}"

monitor = TradingMonitor()

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    await monitor.initialize()
    
    # Start background data update task
    asyncio.create_task(update_loop())

async def update_loop():
    """Background task to update data periodically."""
    while True:
        await monitor.update_data()
        await asyncio.sleep(10)  # Update every 10 seconds

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Trading Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background: #0f1419;
                color: #e6e6e6;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5em;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
                font-size: 1.1em;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .card {{
                background: #1e2328;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                border: 1px solid #2b3139;
            }}
            .card h2 {{
                margin: 0 0 15px 0;
                color: #f0b90b;
                font-size: 1.3em;
            }}
            .metric {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 10px 0;
                padding: 8px 0;
                border-bottom: 1px solid #2b3139;
            }}
            .metric:last-child {{
                border-bottom: none;
            }}
            .metric-value {{
                font-weight: bold;
                font-size: 1.1em;
            }}
            .positive {{ color: #02c076; }}
            .negative {{ color: #f84960; }}
            .neutral {{ color: #848e9c; }}
            .status-running {{ color: #02c076; }}
            .status-error {{ color: #f84960; }}
            .positions-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }}
            .positions-table th,
            .positions-table td {{
                padding: 8px 12px;
                text-align: left;
                border-bottom: 1px solid #2b3139;
            }}
            .positions-table th {{
                background: #2b3139;
                color: #f0b90b;
                font-weight: bold;
            }}
            .auto-refresh {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: #f0b90b;
                color: #000;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: bold;
            }}
            .symbol-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                gap: 10px;
                margin-top: 15px;
            }}
            .symbol-badge {{
                background: #2b3139;
                padding: 8px 12px;
                border-radius: 6px;
                text-align: center;
                font-size: 0.9em;
                border: 1px solid #f0b90b;
            }}
        </style>
    </head>
    <body>
        <div class="auto-refresh">🔄 Auto-refresh: 10s</div>
        
        <div class="container">
            <div class="header">
                <h1>🚀 Live Multi-Symbol Trading Dashboard</h1>
                <p>Monitoring {len(trading_data['symbols'])} cryptocurrency pairs in real-time</p>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h2>📊 Account Balance</h2>
                    <div class="metric">
                        <span>Total Balance:</span>
                        <span class="metric-value" id="total-balance">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>Available:</span>
                        <span class="metric-value" id="free-balance">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>In Use:</span>
                        <span class="metric-value" id="used-balance">Loading...</span>
                    </div>
                </div>
                
                <div class="card">
                    <h2>📈 Performance</h2>
                    <div class="metric">
                        <span>Total P&L:</span>
                        <span class="metric-value" id="total-pnl">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>P&L %:</span>
                        <span class="metric-value" id="total-pnl-pct">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>Open Positions:</span>
                        <span class="metric-value" id="open-positions">Loading...</span>
                    </div>
                </div>
                
                <div class="card">
                    <h2>⚡ System Status</h2>
                    <div class="metric">
                        <span>Bot Status:</span>
                        <span class="metric-value" id="bot-status">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>Last Update:</span>
                        <span class="metric-value" id="last-update">Loading...</span>
                    </div>
                    <div class="metric">
                        <span>Active Symbols:</span>
                        <span class="metric-value">{len(trading_data['symbols'])}</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>💼 Current Positions</h2>
                <div id="positions-container">
                    <p class="neutral">Loading positions...</p>
                </div>
            </div>
            
            <div class="card">
                <h2>🎯 Trading Symbols</h2>
                <div class="symbol-grid">
                    {' '.join([f'<div class="symbol-badge">{symbol.replace("/USDT:USDT", "")}</div>' for symbol in trading_data['symbols']])}
                </div>
            </div>
        </div>
        
        <script>
            async function updateDashboard() {{
                try {{
                    const response = await fetch('/api/data');
                    const data = await response.json();
                    
                    // Update balance
                    document.getElementById('total-balance').textContent = `${{data.balance.total?.toFixed(2) || '0.00'}}`;
                    document.getElementById('free-balance').textContent = `${{data.balance.free?.toFixed(2) || '0.00'}}`;
                    document.getElementById('used-balance').textContent = `${{data.balance.used?.toFixed(2) || '0.00'}}`;
                    
                    // Update performance
                    const totalPnl = data.performance.total_pnl || 0;
                    const totalPnlPct = data.performance.total_pnl_pct || 0;
                    
                    document.getElementById('total-pnl').textContent = `${{totalPnl.toFixed(2)}}`;
                    document.getElementById('total-pnl').className = `metric-value ${{totalPnl >= 0 ? 'positive' : 'negative'}}`;
                    
                    document.getElementById('total-pnl-pct').textContent = `${{totalPnlPct.toFixed(2)}}%`;
                    document.getElementById('total-pnl-pct').className = `metric-value ${{totalPnlPct >= 0 ? 'positive' : 'negative'}}`;
                    
                    document.getElementById('open-positions').textContent = data.performance.open_positions || 0;
                    
                    // Update status
                    document.getElementById('bot-status').textContent = data.status;
                    document.getElementById('bot-status').className = `metric-value ${{data.status === 'running' ? 'status-running' : 'status-error'}}`;
                    
                    const lastUpdate = new Date(data.last_update).toLocaleTimeString();
                    document.getElementById('last-update').textContent = lastUpdate;
                    
                    // Update positions
                    const positionsContainer = document.getElementById('positions-container');
                    if (data.positions && data.positions.length > 0) {{
                        let tableHTML = `
                            <table class="positions-table">
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Size</th>
                                        <th>Entry Price</th>
                                        <th>Mark Price</th>
                                        <th>P&L</th>
                                        <th>P&L %</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        data.positions.forEach(pos => {{
                            const pnlClass = (pos.pnl || 0) >= 0 ? 'positive' : 'negative';
                            const pnlPctClass = (pos.pnl_percentage || 0) >= 0 ? 'positive' : 'negative';
                            
                            tableHTML += `
                                <tr>
                                    <td>${{pos.symbol.replace('/USDT:USDT', '')}}</td>
                                    <td class="${{pos.side === 'long' ? 'positive' : 'negative'}}">${{pos.side?.toUpperCase() || 'N/A'}}</td>
                                    <td>${{pos.size || 'N/A'}}</td>
                                    <td>${{pos.entry_price ? '$' + pos.entry_price.toFixed(4) : 'N/A'}}</td>
                                    <td>${{pos.mark_price ? '$' + pos.mark_price.toFixed(4) : 'N/A'}}</td>
                                    <td class="${{pnlClass}}">${{pos.pnl ? '$' + pos.pnl.toFixed(2) : 'N/A'}}</td>
                                    <td class="${{pnlPctClass}}">${{pos.pnl_percentage ? pos.pnl_percentage.toFixed(2) + '%' : 'N/A'}}</td>
                                </tr>
                            `;
                        }});
                        
                        tableHTML += '</tbody></table>';
                        positionsContainer.innerHTML = tableHTML;
                    }} else {{
                        positionsContainer.innerHTML = '<p class="neutral">No open positions</p>';
                    }}
                    
                }} catch (error) {{
                    console.error('Error updating dashboard:', error);
                }}
            }}
            
            // Update dashboard immediately and then every 10 seconds
            updateDashboard();
            setInterval(updateDashboard, 10000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/api/data")
async def get_data():
    """API endpoint to get current trading data."""
    return trading_data

if __name__ == "__main__":
    print("🌐 Starting Live Trading Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8000")
    print("🔄 Auto-refreshing every 10 seconds")
    print("⚠️  Make sure your trading bot is running in another terminal")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
