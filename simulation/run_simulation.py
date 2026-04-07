"""
run_simulation.py — główny skrypt symulacji.

Uruchomienie: python simulation/run_simulation.py
Wynik:        docs/results/data.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# Dodaj katalog simulation do ścieżki importów
sys.path.insert(0, str(Path(__file__).parent))

import portfolio_config as cfg
from data_fetcher import DataFetcher, build_aligned_returns
from monte_carlo import MonteCarloSimulator
from risk_metrics import RiskMetrics
from stress_testing import StressTester

OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "results" / "data.json"


def main() -> None:
    print("=" * 60)
    print("  Monte Carlo Portfolio Simulation")
    print(f"  Data: {date.today()}")
    print("=" * 60)

    # ── 1. Pobieranie danych ──────────────────────────────────────────────────
    tickers = list(cfg.PORTFOLIO_RAW.keys())
    fetcher = DataFetcher(
        tickers       = tickers,
        eur_tickers   = cfg.EUR_TICKERS,
        gbp_tickers   = cfg.GBP_TICKERS,
        history_years = cfg.HISTORY_YEARS,
        random_seed   = cfg.RANDOM_SEED,
    )
    fetch_result = fetcher.fetch()

    if not fetch_result.assets:
        print("BŁĄD: brak danych dla żadnego tickera. Przerywam.")
        sys.exit(1)

    gbp_usd = fetch_result.gbp_usd
    eur_usd = fetch_result.eur_usd

    # ── 2. Przygotowanie danych portfela ──────────────────────────────────────
    log_returns = build_aligned_returns(fetch_result.assets)
    valid_tickers = [t for t in tickers if t in log_returns.columns]

    FX_MAP = {t: gbp_usd / 100 for t in cfg.GBP_TICKERS}
    FX_MAP.update({t: eur_usd for t in cfg.EUR_TICKERS})

    quantities  = np.array([cfg.PORTFOLIO_RAW[t][0] for t in valid_tickers])
    cost_prices = np.array([cfg.PORTFOLIO_RAW[t][1] for t in valid_tickers])

    S0_local = np.array([
        fetch_result.assets[t].current_price_local for t in valid_tickers
    ])
    fx_factors = np.array([FX_MAP.get(t, 1.0) for t in valid_tickers])
    S0_usd     = S0_local * fx_factors

    portfolio_value_0 = float(S0_usd @ quantities)
    cost_basis        = float(sum(
        cfg.PORTFOLIO_RAW[t][0] * cfg.PORTFOLIO_RAW[t][1] * FX_MAP.get(t, 1.0)
        for t in valid_tickers
    ))

    print(f"\nWartość rynkowa portfela: ${portfolio_value_0:.2f}")
    print(f"Cost basis (USD):         ${cost_basis:.2f}")
    print(f"P&L niezrealizowany:      ${portfolio_value_0- cost_basis:+.2f} "
          f"({(portfolio_value_0 - cost_basis) / cost_basis * 100:+.1f}%)")

    # ── 3. Symulacja ──────────────────────────────────────────────────────────
    simulator = MonteCarloSimulator(
        log_returns       = log_returns[valid_tickers],
        S0                = S0_usd,
        quantities        = quantities,
        portfolio_value_0 = portfolio_value_0,
        n_simulations     = cfg.N_SIMULATIONS,
        simulation_days   = cfg.SIMULATION_DAYS,
        horizons          = cfg.HORIZONS,
        random_seed       = cfg.RANDOM_SEED,
    )
    sim_result = simulator.run()

    # ── 4. Metryki ryzyka ─────────────────────────────────────────────────────
    rm = RiskMetrics(sim_result)

    var_95  = rm.var(0.95)
    var_99  = rm.var(0.99)
    cvar_95 = rm.cvar(0.95)
    probs   = rm.probabilities()
    horizon_summary = rm.multi_horizon_summary()
    drawdowns = rm.drawdown_distribution()

    # ── 5. Stress testing ─────────────────────────────────────────────────────
    tester = StressTester(
        base_simulator    = simulator,
        photonics_tickers = cfg.PHOTONICS_TICKERS,
        eur_tickers       = cfg.EUR_TICKERS,
        gbp_tickers       = cfg.GBP_TICKERS,
    )
    stress_results = tester.run_all()

    # ── 6. Budowanie JSON ─────────────────────────────────────────────────────
    # Alokacja (bieżące ceny rynkowe USD)
    total_market_value = portfolio_value_0
    assets_data = []
    for t in valid_tickers:
        idx     = valid_tickers.index(t)
        val_usd = float(S0_usd[idx] * quantities[idx])
        assets_data.append({
            "ticker":           t,
            "qty":              float(quantities[idx]),
            "price_local":      round(float(S0_local[idx]), 4),
            "price_usd":        round(float(S0_usd[idx]), 4),
            "value_usd":        round(val_usd, 2),
            "weight_pct":       round(val_usd / total_market_value * 100, 2),
            "vol_annual_pct":   round(float(simulator.sigma_annual[idx]) * 100, 2),
            "mu_annual_pct":    round(float(simulator.mu_annual[idx]) * 100, 2),
            "nu":               round(float(simulator.nu[idx]), 2),
            "available_years":  round(fetch_result.assets[t].available_years, 1),
            "bootstrapped_years": round(fetch_result.assets[t].bootstrapped_years, 1),
            "cost_price_local": round(float(cost_prices[idx]), 4),
            "cost_basis_usd":   round(float(cost_prices[idx] * quantities[idx] * FX_MAP.get(t, 1.0)), 2),
        })

    # Histogramy
    final_hist    = rm.histogram(sim_result.final_values)
    drawdown_hist = rm.histogram(drawdowns)

    data = {
        "meta": {
            "run_date":             str(date.today()),
            "portfolio_value_usd":  round(portfolio_value_0, 2),
            "cost_basis_usd":       round(cost_basis, 2),
            "unrealized_pnl_usd":   round(portfolio_value_0 - cost_basis, 2),
            "unrealized_pnl_pct":   round((portfolio_value_0 - cost_basis) / cost_basis * 100, 2),
            "n_simulations":        cfg.N_SIMULATIONS,
            "simulation_days":      cfg.SIMULATION_DAYS,
            "history_years":        cfg.HISTORY_YEARS,
            "gbp_usd":              round(gbp_usd, 4),
            "eur_usd":              round(eur_usd, 4),
            "excluded_tickers":     list(fetch_result.excluded.keys()),
        },
        "assets": assets_data,
        "simulation": {
            "percentile_paths": sim_result.percentile_paths([5, 25, 50, 75, 95]),
            "final_histogram":    final_hist,
            "drawdown_histogram": drawdown_hist,
        },
        "risk_metrics": {
            "var_95":  var_95,
            "var_99":  var_99,
            "cvar_95": cvar_95,
            "probabilities": probs,
            "multi_horizon": horizon_summary,
            "median_end_usd": round(float(np.median(sim_result.final_values)), 2),
            "mean_end_usd":   round(float(sim_result.final_values.mean()), 2),
        },
        "stress_tests": stress_results,
        "correlations": {
            "tickers": valid_tickers,
            "matrix":  [[round(float(v), 3) for v in row]
                        for row in sim_result.corr_matrix],
        },
    }

    # ── 7. Zapis ──────────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nWyniki zapisane do: {OUTPUT_PATH}")
    print(f"VaR 95%: ${var_95['loss_usd']} ({var_95['loss_pct']}%)")
    print(f"VaR 99%: ${var_99['loss_usd']} ({var_99['loss_pct']}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
