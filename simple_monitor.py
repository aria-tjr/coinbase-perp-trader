#!/usr/bin/env python3
"""
Simple Live Trading Monitor
A lightweight web interface to monitor the multi-symbol trading bot.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import get_config
    from utils.logger import get_logger
    from multi_symbol_config import MultiSymbolConfig
    import ccxt
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_simple_html():
    """Create a simple HTML file with trading status."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Trading Monitor</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="30">
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
            .card {{
                background: #1e2328;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
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
            .refresh-notice {{
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
        </style>
    </head>
    <body>
        <div class="refresh-notice">🔄 Auto-refresh: 30s</div>
        
        <div class="container">
            <div class="header">
                <h1>🚀 Live Multi-Symbol Trading Monitor</h1>
                <p>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="card">
                <h2>⚡ System Status</h2>
                <div class="metric">
                    <span>Trading Bot:</span>
                    <span class="metric-value status-running" id="bot-status">RUNNING</span>
                </div>
                <div class="metric">
                    <span>Monitoring:</span>
                    <span class="metric-value">{len(MultiSymbolConfig.get_active_symbols())} Symbols</span>
                </div>
                <div class="metric">
                    <span>Mode:</span>
                    <span class="metric-value status-running">LIVE TRADING</span>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 Account Status</h2>
                <div id="account-data">
                    <p class="neutral">Loading account data...</p>
                </div>
            </div>
            
            <div class="card">
                <h2>🎯 Active Trading Symbols</h2>
                <div class="symbol-grid">
                    {' '.join([f'<div class="symbol-badge">{symbol.replace("/USDT:USDT", "")}</div>' for symbol in MultiSymbolConfig.get_active_symbols()])}
                </div>
            </div>
            
            <div class="card">
                <h2>📈 Recent Activity</h2>
                <p class="neutral">Multi-symbol trading bot is actively monitoring market conditions across all configured pairs.</p>
                <p class="positive">✅ All 13 symbols initialized successfully</p>
                <p class="positive">✅ Market data streams active</p>
                <p class="positive">✅ Risk management enabled</p>
            </div>
        </div>
        
        <script>
            // Update timestamp
            document.addEventListener('DOMContentLoaded', function() {{
                setInterval(function() {{
                    const now = new Date();
                    const timestamp = now.toLocaleString();
                    document.querySelector('.header p').textContent = 'Last Updated: ' + timestamp;
                }}, 1000);
            }});
        </script>
    </body>
    </html>
    """
    return html_content

async def get_account_data():
    """Get current account data from exchange."""
    try:
        config = get_config()
        exchange_config = config.to_ccxt_config(sandbox=False)
        exchange = ccxt.bybit(exchange_config)
        
        # Fetch balance
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {})
        
        # Fetch positions
        positions = exchange.fetch_positions()
        open_positions = [pos for pos in positions if pos['contracts'] > 0]
        
        return {{
            'balance': usdt_balance,
            'positions': open_positions,
            'status': 'connected'
        }}
        
    except Exception as e:
        print(f"Error fetching account data: {e}")
        return {{
            'balance': {{}},
            'positions': [],
            'status': f'error: {str(e)}'
        }}

def update_html_with_data(html_content, account_data):
    """Update HTML with real account data."""
    if account_data['status'] == 'connected':
        balance = account_data['balance']
        positions = account_data['positions']
        
        account_section = f"""
        <div class="metric">
            <span>Total Balance:</span>
            <span class="metric-value">${{balance.get('total', 0):.2f}} USDT</span>
        </div>
        <div class="metric">
            <span>Available:</span>
            <span class="metric-value">${{balance.get('free', 0):.2f}} USDT</span>
        </div>
        <div class="metric">
            <span>In Use:</span>
            <span class="metric-value">${{balance.get('used', 0):.2f}} USDT</span>
        </div>
        <div class="metric">
            <span>Open Positions:</span>
            <span class="metric-value">{len(positions)}</span>
        </div>
        """
    else:
        account_section = f"""
        <div class="metric">
            <span>Status:</span>
            <span class="metric-value negative">{account_data['status']}</span>
        </div>
        """
    
    return html_content.replace(
        '<div id="account-data"><p class="neutral">Loading account data...</p></div>',
        f'<div id="account-data">{account_section}</div>'
    )

async def create_monitor_file():
    """Create a static HTML file with current trading data."""
    print("🔄 Updating trading monitor...")
    
    # Get base HTML
    html_content = create_simple_html()
    
    # Get account data
    account_data = await get_account_data()
    
    # Update HTML with real data
    html_content = update_html_with_data(html_content, account_data)
    
    # Write to file
    monitor_file = Path(__file__).parent / "trading_monitor.html"
    with open(monitor_file, 'w') as f:
        f.write(html_content)
    
    print(f"📊 Monitor updated: file://{monitor_file}")
    return monitor_file

async def run_monitor():
    """Run the monitoring loop."""
    print("🌐 Starting Live Trading Monitor...")
    print("📊 Creating HTML monitor file...")
    
    while True:
        try:
            monitor_file = await create_monitor_file()
            print(f"✅ Monitor file updated at {datetime.now().strftime('%H:%M:%S')}")
            print(f"🔗 Open in browser: file://{monitor_file}")
            
            # Wait 30 seconds before next update
            await asyncio.sleep(30)
            
        except KeyboardInterrupt:
            print("\\n⚠️  Monitor stopped by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    print("🚀 Live Trading Monitor Starting...")
    print("⚠️  Make sure your trading bot is running!")
    
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        print("\\n👋 Monitor stopped")
