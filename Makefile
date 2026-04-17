.PHONY: setup install clean test lint format train backtest run docker-build docker-run

# Variables
PYTHON := python3.11
VENV := venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python

# Setup development environment
setup: clean
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	@echo "✅ Setup complete. Activate virtual environment with: source $(VENV)/bin/activate"

# Install dependencies only
install:
	$(PIP) install -r requirements.txt

# Clean build artifacts
clean:
	rm -rf $(VENV)
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run tests
test:
	$(PYTHON_VENV) -m pytest tests/ -v --cov=core --cov=strategies --cov-report=html

# Lint code
lint:
	$(PYTHON_VENV) -m flake8 core/ strategies/ utils/ --max-line-length=120
	$(PYTHON_VENV) -m mypy core/ strategies/ utils/ --ignore-missing-imports

# Format code
format:
	$(PYTHON_VENV) -m black core/ strategies/ utils/ tests/ --line-length=120

# Train ML models
train:
	@echo "🧠 Training ML models..."
	$(PYTHON_VENV) strategies/ml_predictor.py --train
	$(PYTHON_VENV) strategies/rl_policy.py --train
	@echo "✅ Model training complete"

# Run backtests
backtest:
	@echo "📊 Running backtest on BTC-USDC-PERP..."
	$(PYTHON_VENV) backtest.py \
		--symbol BTC-USDC-PERP \
		--start-date $$(date -d '30 days ago' +%Y-%m-%d) \
		--end-date $$(date +%Y-%m-%d) \
		--initial-capital 10000 \
		--output backtest_results/
	@echo "✅ Backtest complete. Results saved to backtest_results/"

# Run stress test
stress-test:
	@echo "🔥 Running stress test on flash crash scenarios..."
	$(PYTHON_VENV) backtest.py \
		--symbol BTC-USDC-PERP \
		--stress-test \
		--scenario flash-crash \
		--output backtest_results/stress/

# Run live trading (with confirmation)
run:
	@echo "⚠️  WARNING: This will start LIVE TRADING with REAL MONEY!"
	@echo "Press Ctrl+C within 10 seconds to cancel..."
	@sleep 10
	$(PYTHON_VENV) main.py --symbol BTC-USDC-PERP --mode live

# Run paper trading
run-paper:
	@echo "📝 Starting paper trading mode..."
	$(PYTHON_VENV) main.py --symbol BTC-USDC-PERP --mode paper

# Docker support
docker-build:
	docker build -t coinbase-perp-trader:latest .

docker-run:
	docker run -it --rm \
		--env-file .env \
		-v $$(pwd)/logs:/app/logs \
		-v $$(pwd)/data:/app/data \
		coinbase-perp-trader:latest

# Database setup
db-setup:
	@echo "🗄️  Setting up TimescaleDB..."
	$(PYTHON_VENV) infra/database.py --setup

# Monitor system status
monitor:
	@echo "📡 Starting monitoring dashboard..."
	$(PYTHON_VENV) -m uvicorn infra.monitoring:app --reload --port 8000

# Generate performance report
report:
	@echo "📈 Generating performance report..."
	$(PYTHON_VENV) utils/metrics.py --generate-report --output reports/

# Help
help:
	@echo "Available commands:"
	@echo "  make setup        - Set up development environment"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Lint code"
	@echo "  make format       - Format code with black"
	@echo "  make train        - Train ML models"
	@echo "  make backtest     - Run historical backtest"
	@echo "  make stress-test  - Run stress tests"
	@echo "  make run          - Start live trading (⚠️  REAL MONEY)"
	@echo "  make run-paper    - Start paper trading"
	@echo "  make monitor      - Start monitoring dashboard"
	@echo "  make report       - Generate performance report"
