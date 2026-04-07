"""
risk_metrics.py — metryki ryzyka portfela.

Uwaga: VaR jest liczony bez klampowania do 0.
Ujemna wartość VaR oznacza, że nawet w złym scenariuszu portfel jest na zysku.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monte_carlo import SimulationResult


class RiskMetrics:
    """Oblicza metryki ryzyka na podstawie wyników symulacji."""

    def __init__(self, result: SimulationResult):
        self.result  = result
        self.V0      = result.portfolio_value_0
        self.finals  = result.final_values

    # ── VaR ──────────────────────────────────────────────────────────────────

    def var(self, confidence: float = 0.95) -> dict:
        """
        Value at Risk na poziomie ufności `confidence`.
        Zwraca słownik z wartościami w USD i %.
        Ujemna strata = portfel na zysku nawet w tym scenariuszu.
        """
        q = (1 - confidence) * 100
        pct_return = (self.finals - self.V0) / self.V0 * 100
        threshold_pct = float(np.percentile(pct_return, q))
        threshold_usd = self.V0 * threshold_pct / 100

        return {
            "confidence": confidence,
            "loss_pct": round(-threshold_pct, 2),   # dodatni = strata, ujemny = zysk
            "loss_usd": round(-threshold_usd, 2),
            "threshold_value_usd": round(self.V0 + threshold_usd, 2),
        }

    # ── CVaR ─────────────────────────────────────────────────────────────────

    def cvar(self, confidence: float = 0.95) -> dict:
        """Expected Shortfall — średnia straty w najgorszych (1-confidence) scenariuszach."""
        q = (1 - confidence) * 100
        pct_returns = (self.finals - self.V0) / self.V0 * 100
        cutoff = np.percentile(pct_returns, q)
        tail   = pct_returns[pct_returns <= cutoff]

        mean_tail_pct = float(tail.mean())
        mean_tail_usd = self.V0 * mean_tail_pct / 100

        return {
            "confidence": confidence,
            "expected_loss_pct": round(-mean_tail_pct, 2),
            "expected_loss_usd": round(-mean_tail_usd, 2),
        }

    # ── Drawdown ─────────────────────────────────────────────────────────────

    def drawdown_distribution(self) -> np.ndarray:
        """
        Maksymalny drawdown dla każdej ścieżki simulacji.
        Zwraca array (N,) wartości w procentach (dodatnie = drawdown).
        """
        paths    = self.result.portfolio_paths          # (N, T+1)
        peaks    = np.maximum.accumulate(paths, axis=1) # (N, T+1)
        drawdown = (paths - peaks) / peaks * 100        # zawsze <= 0
        max_dd   = drawdown.min(axis=1)                 # (N,) — minimalne (najbardziej negatywne)
        return -max_dd   # zwróć jako wartości dodatnie

    # ── Prawdopodobieństwa ────────────────────────────────────────────────────

    def probabilities(self) -> dict:
        pct_returns = (self.finals - self.V0) / self.V0 * 100
        return {
            "prob_loss":    round(float((self.finals < self.V0).mean() * 100), 1),
            "prob_gain_20": round(float((pct_returns > 20).mean() * 100), 1),
            "prob_loss_30": round(float((pct_returns < -30).mean() * 100), 1),
        }

    # ── Multi-horizon ─────────────────────────────────────────────────────────

    def multi_horizon_summary(self) -> dict:
        """
        Dla każdego horyzontu: percentyle końcowych wartości portfela.
        """
        labels = ["1%", "5%", "10%", "25%", "50%", "75%", "90%", "95%", "99%"]
        pcts   = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        result = {}

        for horizon, finals in self.result.horizon_finals.items():
            vals  = np.percentile(finals, pcts).tolist()
            rets  = ((np.array(vals) - self.V0) / self.V0 * 100).round(1).tolist()
            result[str(horizon)] = {
                "percentiles": {labels[i]: round(vals[i], 2) for i in range(len(labels))},
                "returns_pct":  {labels[i]: rets[i]          for i in range(len(labels))},
                "mean":   round(float(finals.mean()), 2),
                "median": round(float(np.median(finals)), 2),
            }

        return result

    # ── Histogram helper ──────────────────────────────────────────────────────

    @staticmethod
    def histogram(values: np.ndarray, bins: int = 80) -> dict:
        counts, edges = np.histogram(values, bins=bins)
        return {
            "bins":   [round(float(x), 2) for x in edges[:-1]],
            "counts": counts.tolist(),
        }
