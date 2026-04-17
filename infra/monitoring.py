"""Monitoring server for real-time system status."""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn

from utils.logger import get_logger


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle enums and other objects."""
    def default(self, obj):
        if obj is None:
            return "unknown"  # Never return None/null for JSON values
        if isinstance(obj, Enum):
            # Handle MarketRegime and RiskLevel enums explicitly
            if hasattr(obj, 'value'):
                # If value is None/empty, provide a fallback
                if obj.value is None or obj.value == "":
                    if hasattr(obj, '__class__') and obj.__class__.__name__ == 'MarketRegime':
                        return "consolidating"
                    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'RiskLevel':
                        return "moderate" 
                    else:
                        return "unknown"
                return obj.value
            return str(obj)  # Fallback to string representation
        if hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        if hasattr(obj, '__dict__'):  # dataclass or other objects
            return obj.__dict__
        # Handle any other types by converting to string
        try:
            return str(obj)
        except:
            return "unknown"  # Final fallback


app = FastAPI(title="Coinbase Perp Trader Monitor")
logger = get_logger("MonitoringServer")

# Global reference to trading bot
trading_bot = None


@app.get("/")
async def root():
    """Serve monitoring dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Bot Monitor</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background-color: #1a1a1a; 
                color: #e0e0e0;
                margin: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .status-card {
                background-color: #2a2a2a;
                border-radius: 8px;
                padding: 20px;
                margin: 10px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .metric {
                display: inline-block;
                margin: 10px 20px 10px 0;
            }
            .metric-label {
                font-size: 12px;
                color: #888;
                text-transform: uppercase;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                margin-top: 5px;
            }
            .positive { color: #4caf50; }
            .negative { color: #f44336; }
            .neutral { color: #2196f3; }
            .warning { color: #ff9800; }
            h1, h2 { color: #fff; }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #333;
            }
            th { background-color: #333; }
            #ws-status {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 10px 20px;
                border-radius: 20px;
                font-size: 12px;
            }
            .connected { background-color: #4caf50; }
            .disconnected { background-color: #f44336; }
        </style>
    </head>
    <body>
        <div id="ws-status" class="disconnected">Disconnected</div>
        <div class="container">
            <h1>🚀 Coinbase Perpetual Trading Bot Monitor</h1>
            
            <div class="status-card">
                <h2>Account Status</h2>
                <div id="account-metrics"></div>
            </div>
            
            <div class="status-card">
                <h2>Risk Metrics</h2>
                <div id="risk-metrics"></div>
            </div>
            
            <div class="status-card">
                <h2>Strategy Performance</h2>
                <div id="strategy-metrics"></div>
            </div>
            
            <div class="status-card">
                <h2>Open Positions</h2>
                <table id="positions-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Size</th>
                            <th>Entry</th>
                            <th>Current</th>
                            <th>P&L</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody id="positions-body"></tbody>
                </table>
            </div>
            
            <div class="status-card">
                <h2>Recent Orders</h2>
                <table id="orders-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Type</th>
                            <th>Side</th>
                            <th>Size</th>
                            <th>Price</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="orders-body"></tbody>
                </table>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
            const statusEl = document.getElementById('ws-status');
            
            ws.onopen = function() {
                statusEl.textContent = 'Connected';
                statusEl.className = 'connected';
            };
            
            ws.onclose = function() {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'disconnected';
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            function formatNumber(value, decimals = 2) {
                if (value === null || value === undefined || isNaN(value)) return 'N/A';
                const num = parseFloat(value);
                if (!isFinite(num)) return 'N/A';
                return num.toFixed(decimals);
            }

            function formatPercent(value) {
                if (value === null || value === undefined || isNaN(value)) return 'N/A';
                const num = parseFloat(value);
                if (!isFinite(num)) return 'N/A';
                const formatted = (num * 100).toFixed(2);
                return formatted + '%';
            }

            function getColorClass(value) {
                const num = parseFloat(value);
                if (isNaN(num)) return 'neutral';
                if (num > 0) return 'positive';
                if (num < 0) return 'negative';
                return 'neutral';
            }

            function createMetric(label, value, format = 'number', colorize = false) {
                // Handle null/undefined values
                if (value === null || value === undefined) {
                    return `
                        <div class="metric">
                            <div class="metric-label">${label}</div>
                            <div class="metric-value neutral">N/A</div>
                        </div>
                    `;
                }
                
                // Special handling for text format
                if (format === 'text') {
                    // For text values, ensure we have a string and it's not empty
                    const displayValue = value === null || value === undefined || value === '' ? 
                                        'N/A' : String(value);
                    
                    console.log(`Text metric "${label}": ${displayValue}`);
                    
                    return `
                        <div class="metric">
                            <div class="metric-label">${label}</div>
                            <div class="metric-value neutral">${displayValue}</div>
                        </div>
                    `;
                }
                
                // For number formats, check if value is numeric
                if (format !== 'text' && isNaN(value)) {
                    console.log(`Non-numeric value for ${label}: ${value} (type: ${typeof value})`);
                    return `
                        <div class="metric">
                            <div class="metric-label">${label}</div>
                            <div class="metric-value neutral">N/A</div>
                        </div>
                    `;
                }

                const num = parseFloat(value);
                if (!isFinite(num)) {
                    return `
                        <div class="metric">
                            <div class="metric-label">${label}</div>
                            <div class="metric-value neutral">N/A</div>
                        </div>
                    `;
                }

                const colorClass = colorize ? getColorClass(value) : 'neutral';
                const formattedValue = format === 'percent' ? formatPercent(value) : 
                                      format === 'currency' ? '$' + formatNumber(value) :
                                      formatNumber(value);

                return `
                    <div class="metric">
                        <div class="metric-label">${label}</div>
                        <div class="metric-value ${colorClass}">${formattedValue}</div>
                    </div>
                `;
            }
            
            function updateDashboard(data) {
                // Account metrics
                const accountEl = document.getElementById('account-metrics');
                if (data.account) {
                    accountEl.innerHTML = 
                        createMetric('Total Equity', data.account.total_equity, 'currency') +
                        createMetric('Daily P&L', data.account.daily_pnl_pct, 'percent', true) +
                        createMetric('Free Margin', data.account.free_margin, 'currency') +
                        createMetric('Positions', data.account.position_count, 'number');
                }
                
                // Risk metrics
                const riskEl = document.getElementById('risk-metrics');
                if (data.risk) {
                    console.log("Risk data received:", data.risk);
                    
                    // Ensure risk level has a valid value
                    let riskLevel = data.risk.risk_level;
                    if (!riskLevel || riskLevel === null || riskLevel === undefined || riskLevel === "") {
                        riskLevel = "unknown";
                        console.log("Risk level was invalid, set to 'unknown'");
                    }
                    
                    // Convert to string and uppercase for display
                    riskLevel = typeof riskLevel === 'string' ? riskLevel.toUpperCase() : String(riskLevel).toUpperCase();
                    console.log("Formatted risk level:", riskLevel);
                    
                    const riskLevelColor = riskLevel === 'LOW' ? 'positive' : 
                                         riskLevel === 'MODERATE' ? 'neutral' :
                                         riskLevel === 'HIGH' ? 'warning' : 
                                         riskLevel === 'CRITICAL' || riskLevel === 'HALT' ? 'negative' : 'neutral';
                    
                    // Direct HTML instead of using createMetric for risk level
                    const riskLevelHTML = `
                        <div class="metric">
                            <div class="metric-label">Risk Level</div>
                            <div class="metric-value ${riskLevelColor}">${riskLevel}</div>
                        </div>
                    `;
                                         
                    riskEl.innerHTML = 
                        riskLevelHTML +
                        createMetric('Current Leverage', data.risk.current_leverage + 'x', 'text') +
                        createMetric('Daily Drawdown', data.risk.current_drawdown, 'percent', true) +
                        createMetric('VaR (1h)', data.risk.var_1h, 'currency') +
                        createMetric('Sharpe Ratio', data.risk.sharpe_ratio_24h, 'number');
                }
                
                // Strategy metrics
                const strategyEl = document.getElementById('strategy-metrics');
                if (data.strategy) {
                    console.log("Strategy data received:", data.strategy);
                    
                    // Ensure market regime has a valid value
                    let marketRegime = data.strategy.current_regime;
                    if (!marketRegime || marketRegime === null || marketRegime === undefined || marketRegime === "") {
                        marketRegime = "consolidating";
                        console.log("Market regime was invalid, set to 'consolidating' (safer default)");
                    }
                    
                    // Apply color based on regime type
                    let regimeColorClass = "neutral";
                    if (typeof marketRegime === 'string') {
                        const regime = marketRegime.toLowerCase();
                        if (regime === "trending") {
                            regimeColorClass = "positive";
                        } else if (regime === "volatile") {
                            regimeColorClass = "warning";
                        }
                    }
                    
                    // Display as uppercase for better readability
                    marketRegime = typeof marketRegime === 'string' ? marketRegime.toUpperCase() : String(marketRegime).toUpperCase();
                    console.log("Formatted market regime:", marketRegime);
                    
                    // Direct HTML instead of using createMetric for market regime
                    const marketRegimeHTML = `
                        <div class="metric">
                            <div class="metric-label">Market Regime</div>
                            <div class="metric-value ${regimeColorClass}">${marketRegime}</div>
                        </div>
                    `;
                    
                    strategyEl.innerHTML = 
                        marketRegimeHTML +
                        createMetric('Active Signals', data.strategy.active_signals, 'number') +
                        createMetric('Momentum Win Rate', 
                            data.strategy.momentum_win_rate, 'percent') +
                        createMetric('Mean Rev Win Rate', 
                            data.strategy.mean_reversion_win_rate, 'percent');
                }
                
                // Positions table
                const positionsBody = document.getElementById('positions-body');
                if (data.positions) {
                    positionsBody.innerHTML = data.positions.map(pos => `
                        <tr>
                            <td>${pos.symbol}</td>
                            <td class="${pos.side === 'long' ? 'positive' : 'negative'}">
                                ${pos.side.toUpperCase()}
                            </td>
                            <td>${formatNumber(pos.size, 4)}</td>
                            <td>$${formatNumber(pos.entry_price)}</td>
                            <td>$${formatNumber(pos.current_price)}</td>
                            <td class="${getColorClass(pos.unrealized_pnl)}">
                                $${formatNumber(pos.unrealized_pnl)} 
                                (${formatPercent(pos.unrealized_pnl_pct / 100)})
                            </td>
                            <td>${Math.floor(pos.duration_minutes)} min</td>
                        </tr>
                    `).join('') || '<tr><td colspan="7">No open positions</td></tr>';
                }
                
                // Orders table
                const ordersBody = document.getElementById('orders-body');
                if (data.recent_orders) {
                    ordersBody.innerHTML = data.recent_orders.map(order => `
                        <tr>
                            <td>${new Date(order.created_at).toLocaleTimeString()}</td>
                            <td>${order.symbol}</td>
                            <td>${order.type.toUpperCase()}</td>
                            <td class="${order.side === 'buy' ? 'positive' : 'negative'}">
                                ${order.side.toUpperCase()}
                            </td>
                            <td>${formatNumber(order.size, 4)}</td>
                            <td>${order.price ? '$' + formatNumber(order.price) : 'MARKET'}</td>
                            <td>${order.status.toUpperCase()}</td>
                        </tr>
                    `).join('') || '<tr><td colspan="7">No recent orders</td></tr>';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/status")
async def get_status():
    """Get current bot status via API."""
    if not trading_bot:
        return {"status": "not_initialized"}
    
    try:
        # Get all metrics with proper error handling
        try:
            account_risk = trading_bot.risk_manager.get_account_risk_snapshot()
        except Exception as e:
            logger.error(f"Error getting account risk: {e}")
            account_risk = None
            
        try:
            strategy_status = trading_bot.strategy_core.get_strategy_status()
        except Exception as e:
            logger.error(f"Error getting strategy status: {e}")
            strategy_status = None
            
        try:
            positions = trading_bot.execution_engine.position_manager.get_position_summary()
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            positions = []
            
        try:
            orders = trading_bot.execution_engine.order_manager.get_order_summary()
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            orders = []
        
        status = {
            "status": "running" if trading_bot.is_running else "stopped",
            "timestamp": datetime.now().isoformat(),
        }
        
        if account_risk:
            # Handle risk_level properly
            risk_level = getattr(account_risk, 'risk_level', None)
            logger.info(f"Raw risk_level from account_risk: {risk_level}, type: {type(risk_level)}")
            
            if risk_level is None:
                risk_level_str = "unknown"
                logger.info("Risk level is None, setting to 'unknown'")
            elif hasattr(risk_level, 'value'):
                risk_level_str = risk_level.value
                logger.info(f"Extracted risk_level value: {risk_level.value}")
            else:
                risk_level_str = str(risk_level)
                logger.info(f"Converted risk_level to string: {str(risk_level)}")
                
            status.update({
                "account": {
                    "total_equity": getattr(account_risk, 'total_equity', 0.0),
                    "daily_pnl_pct": getattr(account_risk, 'daily_pnl_pct', 0.0),
                    "position_count": getattr(account_risk, 'position_count', 0)
                },
                "risk": {
                    "risk_level": risk_level_str,
                    "current_leverage": getattr(account_risk, 'current_leverage', 0.0),
                    "current_drawdown": getattr(account_risk, 'current_drawdown', 0.0),
                    "var_1h": getattr(account_risk, 'var_1h', 0.0),
                    "sharpe_ratio_24h": getattr(account_risk, 'sharpe_ratio_24h', 0.0)
                }
            })
            
            logger.info(f"Status risk_level: {status['risk'].get('risk_level', 'missing')}")
        else:
            # Provide default values when account_risk is None
            status.update({
                "account": {
                    "total_equity": 0.0,
                    "daily_pnl_pct": 0.0,
                    "position_count": 0
                },
                "risk": {
                    "risk_level": "unknown",
                    "current_leverage": 0.0,
                    "current_drawdown": 0.0,
                    "var_1h": 0.0,
                    "sharpe_ratio_24h": 0.0
                }
            })
        
        if strategy_status:
            status["strategy"] = strategy_status
        else:
            # Provide default strategy status
            status["strategy"] = {
                "active_strategies": [],
                "momentum_win_rate": 0.0,
                "mean_reversion_win_rate": 0.0
            }
        
        status["positions"] = positions if positions is not None else []
        status["orders"] = orders if orders is not None else []
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {"status": "error", "error": str(e)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Check if WebSocket is still connected
            if websocket.client_state.name in ['CLOSED', 'CLOSING']:
                logger.info("WebSocket client disconnected")
                break
                
            if trading_bot and trading_bot.is_running:
                # Get current status with error handling
                try:
                    status = await get_status()
                    
                    # Add detailed position and order info safely
                    if trading_bot.execution_engine:
                        try:
                            positions = trading_bot.execution_engine.position_manager.get_open_positions()
                            status['positions'] = [p.to_dict() for p in positions] if positions else []
                        except Exception as e:
                            logger.error(f"Error getting positions: {e}")
                            status['positions'] = []
                        
                        try:
                            recent_orders = trading_bot.execution_engine.order_manager.get_active_orders()[:10]
                            status['recent_orders'] = [o.to_dict() for o in recent_orders] if recent_orders else []
                        except Exception as e:
                            logger.error(f"Error getting orders: {e}")
                            status['recent_orders'] = []
                        
                        # Calculate strategy-specific win rates safely and ensure market regime is available
                        try:
                            # Get performance data
                            perf = trading_bot.strategy_core.strategy_performance
                            
                            momentum_wr = 0
                            if perf and 'momentum' in perf and perf['momentum']['trades'] > 0:
                                momentum_wr = perf['momentum']['wins'] / perf['momentum']['trades']
                            
                            mr_wr = 0
                            if perf and 'mean_reversion' in perf and perf['mean_reversion']['trades'] > 0:
                                mr_wr = perf['mean_reversion']['wins'] / perf['mean_reversion']['trades']
                            
                            # Ensure strategy key exists
                            if 'strategy' not in status:
                                status['strategy'] = {}
                            
                            # Add win rates
                            status['strategy']['momentum_win_rate'] = momentum_wr
                            status['strategy']['mean_reversion_win_rate'] = mr_wr
                            
                            # Ensure market regime is included and properly serialized
                            if 'current_regime' not in status['strategy'] or status['strategy']['current_regime'] is None:
                                # Try to get it directly from the strategy core
                                current_regime = trading_bot.strategy_core.current_regime
                                
                                # Debug log to see what we're getting
                                logger.info(f"Market regime from strategy_core: {current_regime}, type: {type(current_regime)}")
                                
                                if current_regime is not None:
                                    if hasattr(current_regime, 'value'):
                                        status['strategy']['current_regime'] = current_regime.value
                                        logger.info(f"Extracted market regime value: {current_regime.value}")
                                    else:
                                        status['strategy']['current_regime'] = str(current_regime)
                                        logger.info(f"Converted market regime to string: {str(current_regime)}")
                                else:
                                    status['strategy']['current_regime'] = "unknown"
                                    logger.info("Market regime is None, setting to 'unknown'")
                                
                            # Debug log what's in the status
                            logger.info(f"Strategy status market_regime: {status['strategy'].get('current_regime', 'missing')}")
                            
                        except Exception as e:
                            logger.error(f"Error calculating strategy metrics: {e}")
                    
                    # Debug log relevant status parts before serialization
                    if 'risk' in status:
                        logger.info(f"Pre-serialization risk_level: {status['risk'].get('risk_level')}")
                    if 'strategy' in status:
                        logger.info(f"Pre-serialization market_regime: {status['strategy'].get('current_regime')}")
                    
                    # Double-check and fix any None or Enum values
                    if 'risk' in status and status['risk'].get('risk_level') is None:
                        status['risk']['risk_level'] = 'unknown'
                    if 'strategy' in status and status['strategy'].get('current_regime') is None:
                        status['strategy']['current_regime'] = 'unknown'
                        
                    # Force strings for text fields to avoid number parsing issues in JS
                    if 'risk' in status and 'risk_level' in status['risk']:
                        status['risk']['risk_level'] = str(status['risk']['risk_level'])
                    if 'strategy' in status and 'current_regime' in status['strategy']:
                        status['strategy']['current_regime'] = str(status['strategy']['current_regime'])
                    
                    # Serialize with custom encoder to handle enums
                    try:
                        json_data = json.dumps(status, cls=CustomJSONEncoder)
                        logger.info(f"Successfully serialized status data")
                    except Exception as json_error:
                        logger.error(f"JSON serialization error: {json_error}")
                        # Try a more aggressive approach if the first fails
                        simplified_status = {
                            "status": "running",
                            "timestamp": datetime.now().isoformat(),
                            "account": {
                                "total_equity": status.get('account', {}).get('total_equity', 0.0),
                                "daily_pnl_pct": status.get('account', {}).get('daily_pnl_pct', 0.0)
                            },
                            "risk": {
                                "risk_level": "unknown", 
                                "current_leverage": 0.0
                            },
                            "strategy": {
                                "current_regime": "unknown",
                                "active_signals": 0
                            }
                        }
                        json_data = json.dumps(simplified_status)
                    
                    # Check WebSocket state before sending
                    if websocket.client_state.name not in ['CLOSED', 'CLOSING']:
                        await websocket.send_text(json_data)
                        logger.info(f"Data sent to WebSocket client")
                    else:
                        logger.info("WebSocket closed during send, exiting")
                        break  # Exit loop if WebSocket is closed
                    
                except Exception as e:
                    # More robust error message formatting
                    error_type = type(e).__name__ if hasattr(type(e), '__name__') else "Unknown"
                    error_str = str(e) if str(e) else repr(e) if repr(e) != str(e) else "No error details"
                    error_msg = f"Error preparing status data: {error_type}: {error_str}"
                    
                    # Only log full traceback for non-WebSocket errors
                    if "WebSocketDisconnect" not in error_type and "ClientDisconnected" not in error_type:
                        import traceback
                        traceback_str = traceback.format_exc()
                        logger.error(f"{error_msg}\nTraceback:\n{traceback_str}")
                    else:
                        logger.info(f"WebSocket disconnected: {error_msg}")
                        break  # Exit cleanly on disconnect
                    
                    # Send minimal status on error only if connection is open
                    try:
                        if websocket.client_state.name not in ['CLOSED', 'CLOSING']:
                            await websocket.send_text(json.dumps({
                                "status": "error", 
                                "timestamp": datetime.now().isoformat(),
                                "error": error_msg
                            }))
                    except Exception as send_error:
                        logger.info(f"Failed to send error message (connection likely closed): {send_error}")
                        break  # Exit if can't send error message
            else:
                # Send status when bot is not running
                try:
                    if websocket.client_state.name not in ['CLOSED', 'CLOSING']:
                        await websocket.send_text(json.dumps({
                            "status": "stopped",
                            "timestamp": datetime.now().isoformat()
                        }))
                except Exception as e:
                    logger.info(f"Failed to send stopped status: {e}")
                    break
            
            await asyncio.sleep(1)  # Update every second
            
    except Exception as e:
        if "WebSocketDisconnect" in str(type(e)) or "ClientDisconnected" in str(type(e)):
            logger.info(f"WebSocket connection closed: {e}")
        else:
            logger.error(f"WebSocket error: {e}")
        try:
            if websocket.client_state.name not in ['CLOSED', 'CLOSING']:
                await websocket.close(code=1001, reason="Server error")
        except Exception as close_error:
            logger.debug(f"Error closing WebSocket: {close_error}")
    finally:
        logger.info("WebSocket connection ended")


async def start_monitoring_server(bot):
    """Start the monitoring server."""
    global trading_bot
    trading_bot = bot
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,  # Standard port for monitoring
        log_level="error"
    )
    server = uvicorn.Server(config)
    
    logger.info("Starting monitoring server on http://localhost:8000")
    await server.serve()
