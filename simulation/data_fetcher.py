"""
data_fetcher.py — pobieranie danych rynkowych z yfinance.

Obsługa brakującej historii:
  - >= 10 lat: używa pełnej historii
  - 2-10 lat:  dopełnia bootstrap (resample z replacement) do 10 lat
  - < 2 lat:   wyklucza ticker z ostrzeżeniem
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


@dataclass
class AssetData:
    ticker: str
    log_returns: pd.Series          # dzienna seria log-zwrotów (10 lat)
    current_price_local: float      # ostatnia cena w walucie lokalnej
    available_years: float          # ile lat rzeczywistych danych
    bootstrapped_years: float       # ile lat uzupełniono bootstrapem (0 = brak)


@dataclass
class FetchResult:
    assets: dict[str, AssetData] = field(default_factory=dict)
    excluded: dict[str, str]     = field(default_factory=dict)  # ticker → powód
    gbp_usd: float = 1.0
    eur_usd: float = 1.0


class DataFetcher:
    """Pobiera i przygotowuje dane dla portfela."""

    def __init__(
        self,
        tickers: list[str],
        eur_tickers: list[str],
        gbp_tickers: list[str],
        history_years: int = 10,
        random_seed: int = 42,
    ):
        self.tickers       = tickers
        self.eur_tickers   = eur_tickers
        self.gbp_tickers   = gbp_tickers
        self.history_years = history_years
        self.rng           = np.random.default_rng(random_seed)

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch(self) -> FetchResult:
        result = FetchResult()
        result.gbp_usd, result.eur_usd = self._fetch_fx()

        for ticker in self.tickers:
            asset = self._fetch_ticker(ticker)
            if asset is None:
                result.excluded[ticker] = "za mało danych (< 2 lata)"
            else:
                result.assets[ticker] = asset

        self._print_report(result)
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_fx(self) -> tuple[float, float]:
        print("Pobieranie kursów walut...")
        try:
            fx = yf.download(
                ["GBPUSD=X", "EURUSD=X"],
                period="5d",
                auto_adjust=True,
                progress=False,
            )["Close"]
            gbp = float(fx["GBPUSD=X"].dropna().iloc[-1])
            eur = float(fx["EURUSD=X"].dropna().iloc[-1])
            print(f"  GBP/USD = {gbp:.4f}  |  EUR/USD = {eur:.4f}")
            return gbp, eur
        except Exception as e:
            print(f"  UWAGA: nie udało się pobrać FX ({e}), używam domyślnych 1.30 / 1.10")
            return 1.30, 1.10

    def _fetch_ticker(self, ticker: str) -> AssetData | None:
        try:
            raw = yf.download(
                ticker,
                period=f"{self.history_years}y",
                auto_adjust=True,
                progress=False,
            )["Close"]
            # yfinance może zwrócić DataFrame z MultiIndex kolumn — spłaszcz do Series
            if isinstance(raw, pd.DataFrame):
                raw = raw.iloc[:, 0]
            raw = raw.dropna()
        except Exception as e:
            print(f"  {ticker}: błąd pobierania — {e}")
            return None

        if raw.empty or len(raw) < 50:
            return None

        available_days  = len(raw)
        available_years = available_days / 252.0
        target_days     = self.history_years * 252

        log_ret = np.log(raw / raw.shift(1)).dropna()

        if available_years < 2.0:
            return None

        bootstrapped_years = 0.0
        if available_days < target_days:
            gap = target_days - available_days
            bootstrapped_years = gap / 252.0
            # Generuj daty przed wyliczeniem próbki, aby mieć gwarantowaną zgodność rozmiarów
            fake_dates = pd.bdate_range(
                end=log_ret.index[0] - pd.Timedelta(days=1),
                periods=gap,
            )
            sampled = log_ret.sample(
                n=len(fake_dates), replace=True,
                random_state=int(self.rng.integers(1e6)),
            )
            sampled = pd.Series(sampled.values, index=fake_dates, name=log_ret.name)
            log_ret = pd.concat([sampled, log_ret]).sort_index()

        return AssetData(
            ticker=ticker,
            log_returns=log_ret,
            current_price_local=float(raw.iloc[-1]),
            available_years=available_years,
            bootstrapped_years=bootstrapped_years,
        )

    def _print_report(self, result: FetchResult) -> None:
        print("\nRaport dostępności danych:")
        print(f"  {'Ticker':10s} {'Lat real.':>10s} {'Lat bootstrap':>15s} {'Status':>10s}")
        print("  " + "-" * 50)
        for t, asset in result.assets.items():
            status = "OK" if asset.bootstrapped_years == 0 else "bootstrap"
            print(
                f"  {t:10s} {asset.available_years:>10.1f} "
                f"{asset.bootstrapped_years:>15.1f} {status:>10s}"
            )
        for t, reason in result.excluded.items():
            print(f"  {t:10s} {'—':>10s} {'—':>15s} {'WYKLUCZONY':>10s}  ({reason})")


def build_aligned_returns(assets: dict[str, AssetData]) -> pd.DataFrame:
    """
    Wyrównuje log-zwroty wszystkich aktywów do wspólnego indeksu (inner join).
    Zwraca DataFrame: kolumny = tickery, indeks = daty.
    """
    series = {t: a.log_returns for t, a in assets.items()}
    df = pd.DataFrame(series).dropna(how="all").ffill().dropna()
    return df
