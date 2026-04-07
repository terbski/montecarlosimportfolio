"""
monte_carlo.py — Symulacja Monte Carlo (GBM + t-Student + Cholesky).

Model:
  - Parametry μ i σ estymowane przez MLE rozkładu t-Studenta (scipy.stats.t)
  - Generowanie skorelowanych szokow przez dekompozycję Cholesky'ego
  - Przyspieszenie: wektoryzacja numpy zamiast pętli po symulacjach
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


class MonteCarloSimulator:
    """
    Uruchamia symulację Monte Carlo portfela akcji.

    Parameters
    ----------
    log_returns : pd.DataFrame
        Dzienne log-zwroty (wiersze = daty, kolumny = tickery).
    S0 : np.ndarray
        Aktualne ceny w USD, w kolejności kolumn log_returns.
    quantities : np.ndarray
        Liczby akcji, w kolejności kolumn log_returns.
    portfolio_value_0 : float
        Bieżąca wartość portfela w USD.
    n_simulations : int
    simulation_days : int
    horizons : list[int]
        Horyzonty (w dniach) dla których zbieramy końcowe wartości.
    random_seed : int
    """

    def __init__(
        self,
        log_returns: pd.DataFrame,
        S0: np.ndarray,
        quantities: np.ndarray,
        portfolio_value_0: float,
        n_simulations: int = 10_000,
        simulation_days: int = 252,
        horizons: list[int] | None = None,
        random_seed: int = 42,
    ):
        self.log_returns       = log_returns
        self.S0                = S0
        self.quantities        = quantities
        self.portfolio_value_0 = portfolio_value_0
        self.n_simulations     = n_simulations
        self.simulation_days   = simulation_days
        self.horizons          = horizons or [21, 63, 126, 252]
        self.random_seed       = random_seed

        self.tickers   = list(log_returns.columns)
        self.n_assets  = len(self.tickers)

        self._fit_params()
        self._fit_cholesky()

    # ── Fit ──────────────────────────────────────────────────────────────────

    def _fit_params(self) -> None:
        """MLE t-Student per asset → mu_daily, sigma_daily, nu."""
        self.mu_daily    = np.empty(self.n_assets)
        self.sigma_daily = np.empty(self.n_assets)
        self.nu          = np.empty(self.n_assets)

        for i, ticker in enumerate(self.tickers):
            series = self.log_returns[ticker].dropna().values
            nu, loc, scale = stats.t.fit(series)
            self.nu[i]          = max(nu, 2.1)   # zapobiegaj nu < 2 (nieskończona wariancja)
            self.mu_daily[i]    = loc
            self.sigma_daily[i] = scale

        # Annualizacja dla raportowania
        self.mu_annual    = self.mu_daily    * 252
        self.sigma_annual = self.sigma_daily * np.sqrt(252)

    def _fit_cholesky(self) -> None:
        """Macierz korelacji i dekompozycja Cholesky'ego."""
        cov = self.log_returns.cov().values.copy()
        # Regularyzacja: dodaj małą wartość na diagonali dla stabilności numerycznej
        cov += np.eye(self.n_assets) * 1e-10
        self.cov_matrix  = cov
        self.corr_matrix = self.log_returns.corr().values
        self.L           = np.linalg.cholesky(cov)

    # ── Simulation ───────────────────────────────────────────────────────────

    def run(self) -> SimulationResult:
        """
        Uruchamia N symulacji wektorowo.

        Returns
        -------
        SimulationResult z pełnymi ścieżkami i końcowymi wartościami per horyzont.
        """
        print(f"Uruchamiam {self.n_simulations:,} symulacji × {self.simulation_days} dni "
              f"({self.n_assets} aktywów, model: t-Student)...")

        rng = np.random.default_rng(self.random_seed)
        T   = self.simulation_days
        N   = self.n_simulations
        A   = self.n_assets

        # Generowanie wszystkich szokow naraz: (N, T, A)
        Z_indep = rng.standard_normal((N, T, A))

        # Korelacja przez Cholesky: Z_corr[n,t,:] = L @ Z_indep[n,t,:]
        # Efektywnie: (N, T, A) @ L.T → (N, T, A)
        Z_corr = Z_indep @ self.L.T

        # Skalowanie do t-Studenta: dziel przez sqrt(chi2(nu)/nu)
        # Używamy minimalnego nu dla portfela (zachowawcze)
        nu_min  = float(np.min(self.nu))
        chi2    = rng.chisquare(df=nu_min, size=(N, T, 1))
        scaling = np.sqrt(chi2 / nu_min)
        Z_t     = Z_corr / scaling  # (N, T, A) — grubsze ogony

        # GBM: drift + diffusion
        drift     = (self.mu_daily - 0.5 * self.sigma_daily ** 2)  # (A,)
        diffusion = self.sigma_daily                                 # (A,)

        log_ret_sim = drift + diffusion * Z_t   # (N, T, A)

        # Ścieżki cen: (N, T, A)
        cum_log_ret  = np.cumsum(log_ret_sim, axis=1)
        price_paths  = self.S0 * np.exp(cum_log_ret)  # (N, T, A)

        # Wartości portfela: (N, T+1)
        portfolio_paths         = np.empty((N, T + 1))
        portfolio_paths[:, 0]   = self.portfolio_value_0
        portfolio_paths[:, 1:]  = price_paths @ self.quantities  # (N, T)

        # Końcowe wartości per horyzont
        horizon_finals = {}
        for h in self.horizons:
            t_idx = min(h, T)
            horizon_finals[h] = portfolio_paths[:, t_idx]

        print("Symulacja zakończona.")
        return SimulationResult(
            portfolio_paths   = portfolio_paths,
            horizon_finals    = horizon_finals,
            portfolio_value_0 = self.portfolio_value_0,
            tickers           = self.tickers,
            mu_annual         = self.mu_annual,
            sigma_annual      = self.sigma_annual,
            nu                = self.nu,
            corr_matrix       = self.corr_matrix,
        )


class SimulationResult:
    """Wyniki symulacji Monte Carlo."""

    def __init__(
        self,
        portfolio_paths: np.ndarray,
        horizon_finals: dict[int, np.ndarray],
        portfolio_value_0: float,
        tickers: list[str],
        mu_annual: np.ndarray,
        sigma_annual: np.ndarray,
        nu: np.ndarray,
        corr_matrix: np.ndarray,
    ):
        self.portfolio_paths   = portfolio_paths    # (N, T+1)
        self.horizon_finals    = horizon_finals     # {days: (N,)}
        self.portfolio_value_0 = portfolio_value_0
        self.tickers           = tickers
        self.mu_annual         = mu_annual
        self.sigma_annual      = sigma_annual
        self.nu                = nu
        self.corr_matrix       = corr_matrix

    @property
    def final_values(self) -> np.ndarray:
        return self.portfolio_paths[:, -1]

    def percentile_paths(self, percentiles: list[int] = [5, 25, 50, 75, 95]) -> dict[str, list[float]]:
        """Percentyle ścieżek dla wykresu fan chart."""
        return {
            f"p{p}": np.percentile(self.portfolio_paths, p, axis=0).tolist()
            for p in percentiles
        }
