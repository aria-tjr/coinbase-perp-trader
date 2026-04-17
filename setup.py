"""Setup configuration for Coinbase Perpetual Trading System."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="coinbase-perp-trader",
    version="0.1.0",
    author="Trading Bot",
    description="Aggressive perpetual futures trading system for Coinbase International Exchange",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/coinbase-perp-trader",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
"console_scripts": [
    "bybit-trader=main:main",
    "bybit-backtest=backtest:main",
],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml"],
    },
)
