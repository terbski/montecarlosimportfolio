"""
stress_testing.py — scenariusze szokowe dla portfela.

Każdy scenariusz aplikuje szok do cen startowych S0 i ponownie uruchamia
uproszczoną symulację (te same parametry μ/σ, nowe S0).
"""

from __future__ import annotations

import numpy as np

from monte_carlo import MonteCarloSimulator, SimulationResult


SCENARIOS = [
    {
        "name":        "Crash rynkowy",
        "description": "Wszystkie aktywa tracą 30% wartości jednocześnie",
        "type":        "global",
        "shock":       0.70,  # mnożnik S0
    },
    {
        "name":        "Szok sektorowy fotoniki",
        "description": "Spółki fotoniki/półprzewodnikowe -40%, IVV bez zmian",
        "type":        "sector",
        "shock":       0.60,  # dla PHOTONICS_TICKERS
    },
    {
        "name":        "Szok walutowy (GBP/EUR -15%)",
        "description": "Deprecjacja GBP i EUR o 15% wobec USD",
        "type":        "fx",
        "shock":       0.85,  # mnożnik dla aktywów GBP/EUR
    },
    {
        "name":        "Stagflacja",
        "description": "Oczekiwane zwroty o 50% niższe, zmienność +30%",
        "type":        "params",
        "mu_factor":   0.50,
        "sigma_factor": 1.30,
    },
]


class StressTester:
    """Uruchamia scenariusze szokowe."""

    def __init__(
        self,
        base_simulator: MonteCarloSimulator,
        photonics_tickers: list[str],
        eur_tickers: list[str],
        gbp_tickers: list[str],
    ):
        self.sim               = base_simulator
        self.photonics_tickers = photonics_tickers
        self.eur_tickers       = eur_tickers
        self.gbp_tickers       = gbp_tickers

    def run_all(self) -> list[dict]:
        results = []
        for scenario in SCENARIOS:
            res = self._run_scenario(scenario)
            results.append(res)
        return results

    # ── Private ───────────────────────────────────────────────────────────────

    def _run_scenario(self, scenario: dict) -> dict:
        V0     = self.sim.portfolio_value_0
        S0     = self.sim.S0.copy()
        qty    = self.sim.quantities
        tickers = self.sim.tickers

        shocked_S0     = S0.copy()
        shocked_mu     = self.sim.mu_daily.copy()
        shocked_sigma  = self.sim.sigma_daily.copy()

        stype = scenario["type"]

        if stype == "global":
            shocked_S0 = S0 * scenario["shock"]

        elif stype == "sector":
            for i, t in enumerate(tickers):
                if t in self.photonics_tickers:
                    shocked_S0[i] = S0[i] * scenario["shock"]

        elif stype == "fx":
            fx_shock = scenario["shock"]
            for i, t in enumerate(tickers):
                if t in self.eur_tickers or t in self.gbp_tickers:
                    shocked_S0[i] = S0[i] * fx_shock

        elif stype == "params":
            shocked_mu    = self.sim.mu_daily    * scenario["mu_factor"]
            shocked_sigma = self.sim.sigma_daily * scenario["sigma_factor"]

        shocked_V0 = float(shocked_S0 @ qty)

        # Szybka symulacja z nowymi S0/parametrami (1000 ścieżek wystarczy do raportowania)
        stressed = MonteCarloSimulator(
            log_returns       = self.sim.log_returns,
            S0                = shocked_S0,
            quantities        = qty,
            portfolio_value_0 = shocked_V0,
            n_simulations     = 2_000,
            simulation_days   = self.sim.simulation_days,
            horizons          = [self.sim.simulation_days],
            random_seed       = self.sim.random_seed,
        )
        # Nadpisz parametry jeśli stagflacja
        if stype == "params":
            stressed.mu_daily    = shocked_mu
            stressed.sigma_daily = shocked_sigma
            # Przelicz drift/diffusion są używane w run(), więc nadpisujemy
            stressed.mu_annual    = shocked_mu    * 252
            stressed.sigma_annual = shocked_sigma * np.sqrt(252)

        sim_result  = stressed.run()
        final_vals  = sim_result.final_values
        median_end  = float(np.median(final_vals))
        pct_change  = (shocked_V0 - V0) / V0 * 100

        var_95_pct = float(np.percentile((final_vals - shocked_V0) / shocked_V0 * 100, 5))

        return {
            "name":              scenario["name"],
            "description":       scenario["description"],
            "shocked_value_usd": round(shocked_V0, 2),
            "immediate_pnl_pct": round(pct_change, 1),
            "median_end_usd":    round(median_end, 2),
            "var_95_pct":        round(-var_95_pct, 1),
        }
