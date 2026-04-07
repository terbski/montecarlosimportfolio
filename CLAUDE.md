# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **OS:** Windows 11, shell: bash (Unix syntax)
- **Python:** `C:\Python314\` (Python 3.14)
- **Jupyter:** installed globally via pip

## Key Project: Monte Carlo Portfolio Simulation

**File:** `C:/Users/Ignac/Documents/monte_carlo_portfolio.ipynb`

A 25 000-simulation Monte Carlo risk analysis of a 9-asset investment portfolio using Geometric Brownian Motion with correlated returns (Cholesky decomposition). Simulation horizon: 2 trading years (504 days).

### Running the notebook

```bash
# Execute all cells and save in-place
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=180 \
  "C:/Users/Ignac/Documents/monte_carlo_portfolio.ipynb" \
  --output monte_carlo_portfolio.ipynb

# Open in browser
jupyter notebook "C:/Users/Ignac/Documents/monte_carlo_portfolio.ipynb"
```

### Dependencies

```bash
pip install numpy pandas matplotlib seaborn yfinance scipy jupyter
```

### Notebook architecture (6 sections)

| Section | Purpose |
|---|---|
| 1 | Portfolio definition — `PORTFOLIO_RAW` dict: `{ticker: (qty, purchase_price)}` |
| 2 | yfinance data download + FX conversion to USD + μ/σ estimation |
| 3 | Correlation heatmap |
| 4 | GBM simulation loop — produces `portfolio_paths` array `(25000, 505)` |
| 5 | Risk metrics: VaR 95/99%, CVaR, percentile distribution |
| 6 | Visualizations: fan chart, histogram, risk contribution, volatility bar |

### Currency handling

Yahoo Finance returns prices in local currency. Conversions applied in Section 2:

- `IQE.L` (LSE): prices in **GBp (pence)** → divide by 100, multiply by GBP/USD
- `SOI.PA`, `M7U.DE`, `P4O.DE`: prices in **EUR** → multiply by EUR/USD
- USD tickers (AAOI, AXTI, LITE, LNSR, IVV): no conversion

FX rates fetched live via `yfinance.download(['GBPUSD=X', 'EURUSD=X'], period='5d')`.

### Portfolio tickers

| Ticker | Company | Exchange |
|---|---|---|
| M7U.DE | Nynomic | XETRA |
| AAOI | Applied Optoelectronics | NASDAQ |
| AXTI | AXT Inc | NASDAQ |
| SOI.PA | Soitec | Euronext Paris |
| IQE.L | IQE | LSE (prices in GBp) |
| LITE | Lumentum | NASDAQ |
| LNSR | LENSAR | NASDAQ |
| IVV | iShares Core S&P 500 ETF | NYSE |
| P4O.DE | Plan Optik | XETRA |

### Key variables (available after Section 2)

- `S0` — current market prices in USD (array, ordered as `portfolio_tickers`)
- `portfolio_value_0` — current total market value in USD
- `portfolio_tickers` — ordered list of valid tickers
- `quantities` — share counts matching `portfolio_tickers` order
- `mu_daily`, `sigma_daily` — per-asset daily return parameters
- `log_returns` — DataFrame of historical daily log-returns
