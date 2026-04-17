#!/usr/bin/env python3
"""
Simple monitor for trading system.
"""

import sys
import os
from datetime import datetime
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print header."""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          Multi-Symbol Trading Monitor                         ║")
    print("║                                                               ║")
    print(f"║  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                  ║")
    print("╚═══════════════════════════════════════════════════════════════╝")

def check_bot_process():
    """Check if the bot is running."""
    import subprocess
    
    try:
        # Run ps command to find bot process
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        output = result.stdout
        
        # Check for multi_symbol_bot.py in process list
        bot_processes = [line for line in output.splitlines() if 'multi_symbol_bot.py' in line and 'python' in line]
        
        if bot_processes:
            print("\n✅ Bot is running")
            for process in bot_processes:
                parts = process.split()
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                start_time = parts[9]
                print(f"   PID: {pid}, CPU: {cpu}%, MEM: {mem}%, Started: {start_time}")
        else:
            print("\n❌ Bot is not running")
        
        return len(bot_processes) > 0
    except Exception as e:
        print(f"Error checking bot process: {e}")
        return False

def check_log_file():
    """Check the trading log file for recent entries."""
    log_path = Path(__file__).parent / "logs" / "trading.log"
    
    try:
        if log_path.exists():
            # Get file stats
            import datetime as dt
            modified_time = dt.datetime.fromtimestamp(log_path.stat().st_mtime)
            size_mb = log_path.stat().st_size / (1024 * 1024)
            
            print(f"\n📝 Log file: {log_path.name}")
            print(f"   Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')} ({get_time_ago(modified_time)})")
            print(f"   Size: {size_mb:.2f} MB")
            
            # Read recent log entries
            print("\n📋 Recent log entries:")
            print("-" * 80)
            
            # Use tail command for efficiency
            import subprocess
            result = subprocess.run(['tail', '-n', '10', str(log_path)], 
                                    capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if "ERROR" in line:
                    print(f"\033[91m{line}\033[0m")  # Red for errors
                elif "WARNING" in line:
                    print(f"\033[93m{line}\033[0m")  # Yellow for warnings
                else:
                    print(line)
                    
            print("-" * 80)
            return True
        else:
            print("\n❌ Log file not found")
            return False
    except Exception as e:
        print(f"Error reading log file: {e}")
        return False

def get_time_ago(dt):
    """Format time difference as human-readable string."""
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} days ago"
    
    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours} hours ago"
    
    minutes = (diff.seconds % 3600) // 60
    if minutes > 0:
        return f"{minutes} minutes ago"
    
    return f"{diff.seconds} seconds ago"

def check_trading_conditions():
    """Check if trading conditions are favorable."""
    print("\n🔍 TRADING CONDITIONS")
    print("-" * 50)
    
    # Check if market is open (crypto is 24/7)
    print("✅ Market is open (24/7)")
    
    # Check time of day
    hour = datetime.now().hour
    if 0 <= hour < 4:
        print("⚠️ Low volatility period (0:00-4:00 UTC)")
    elif 12 <= hour < 16:
        print("✅ High volatility period (12:00-16:00 UTC)")
    else:
        print("✓ Normal trading hours")
    
    # Check day of week
    day = datetime.now().weekday()
    if day == 5:  # Saturday
        print("⚠️ Weekend trading (Saturday)")
    elif day == 6:  # Sunday
        print("⚠️ Weekend trading (Sunday)")
    else:
        print("✅ Weekday trading")

def check_config_params():
    """Check config parameters."""
    from multi_symbol_config import MultiSymbolConfig
    
    print("\n⚙️ CONFIGURATION")
    print("-" * 50)
    
    symbols = MultiSymbolConfig.get_active_symbols()
    print(f"Active symbols: {len(symbols)} pairs")
    print(f"Total allocation: {MultiSymbolConfig.get_total_position_allocation():.1%}")
    print(f"Max exposure: {MultiSymbolConfig.get_risk_config()['max_total_exposure']:.1%}")
    print(f"Max concurrent positions: {MultiSymbolConfig.get_risk_config()['max_concurrent_positions']}")
    print(f"Max active symbols: {MultiSymbolConfig.get_risk_config()['max_symbols_active']}")
    
    # Print first few symbols
    if symbols:
        print("\nTop priority symbols:")
        for i, symbol in enumerate(symbols[:5]):
            config = MultiSymbolConfig.get_symbol_config(symbol)
            print(f"  {symbol.replace('/USDT:USDT', '')}: {config['position_size_pct']:.1%} allocation, " +
                  f"{config['base_leverage']}x leverage")

def monitor():
    """Run monitoring continuously."""
    try:
        running = True
        start_time = datetime.now()
        refresh_interval = 10  # seconds
        
        while running:
            clear_screen()
            print_header()
            
            # Print uptime
            uptime = datetime.now() - start_time
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"🕒 Monitor uptime: {hours:02}:{minutes:02}:{seconds:02}")
            
            # Check if bot is running
            bot_running = check_bot_process()
            
            # Check log file for activity
            log_exists = check_log_file()
            
            # Check trading conditions
            check_trading_conditions()
            
            # Check configuration
            check_config_params()
            
            # Command options
            print("\n💻 COMMANDS")
            print("-" * 50)
            print("r - Refresh now")
            print("q - Quit monitor")
            print(f"\nRefreshing in {refresh_interval} seconds... Press Ctrl+C to quit")
            
            # Wait with timeout for key press
            import select
            import sys
            
            i, o, e = select.select([sys.stdin], [], [], refresh_interval)
            if i:
                key = sys.stdin.readline().strip()
                if key.lower() == 'q':
                    print("Exiting monitor...")
                    running = False
                elif key.lower() == 'r':
                    continue
            
    except KeyboardInterrupt:
        print("\nExiting monitor...")
    except Exception as e:
        print(f"Error in monitor: {e}")

if __name__ == "__main__":
    monitor()
