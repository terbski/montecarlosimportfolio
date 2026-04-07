# ============================================================
#  KONFIGURACJA PORTFELA — JEDYNY PLIK DO EDYCJI
#  Aby przeanalizować nowy portfel:
#    1. Zmień PORTFOLIO_RAW na swoje aktywa
#    2. Uruchom: python simulation/run_simulation.py
#    3. Otwórz docs/index.html w przeglądarce (lub wróci GitHub Actions)
#
#  Format: 'TICKER': (ilość_akcji, cena_zakupu_w_walucie_lokalnej)
#  Waluty lokalne:
#    LSE (np. IQE.L)       → cena w GBp (pencach)
#    XETRA / Euronext      → cena w EUR
#    NASDAQ / NYSE         → cena w USD
# ============================================================

PORTFOLIO_RAW: dict[str, tuple[float, float]] = {
    'M7U.DE':  (10.0,  11.39),   # Nynomic — XETRA (EUR)
    'AAOI':    (1.2,  102.02),   # Applied Optoelectronics — NASDAQ (USD)
    'AXTI':    (3.0,   48.00),   # AXT Inc — NASDAQ (USD)
    'SOI.PA':  (2.1,   54.38),   # Soitec — Euronext Paris (EUR)
    'IQE.L':   (270.0,  0.2521), # IQE — LSE (GBp)
    'LITE':    (0.09, 674.90),   # Lumentum — NASDAQ (USD)
    'LNSR':    (6.0,    6.08),   # LENSAR — NASDAQ (USD)
    'IVV':     (0.02, 609.56),   # iShares Core S&P 500 ETF — NYSE (USD)
    'P4O.DE':  (1.0,    8.50),   # Plan Optik — XETRA (EUR)
}

# ── Parametry symulacji ───────────────────────────────────────────────────────
N_SIMULATIONS:   int  = 25_000   # liczba ścieżek Monte Carlo
HISTORY_YEARS:   int  = 10       # lat historii (pobiera maks. dostępne jeśli spółka krócej istnieje)
SIMULATION_DAYS: int  = 504      # horyzont symulacji (dni handlowe) — 2 lata
HORIZONS:        list = [21, 63, 126, 252, 504]  # horyzonty analizy: 1m, 3m, 6m, 1r, 2l
RANDOM_SEED:     int  = 42

# ── Mapowanie walut ───────────────────────────────────────────────────────────
# Tickery których ceny Yahoo Finance zwraca w EUR
EUR_TICKERS: list = ['SOI.PA', 'M7U.DE', 'P4O.DE']
# Tickery których ceny Yahoo Finance zwraca w GBp (pencach, nie funtach)
GBP_TICKERS: list = ['IQE.L']
# Pozostałe zakładamy USD

# ── Sektorowe grupy do stress testingu ───────────────────────────────────────
PHOTONICS_TICKERS: list = ['AAOI', 'AXTI', 'IQE.L', 'LITE', 'SOI.PA', 'M7U.DE', 'P4O.DE']
