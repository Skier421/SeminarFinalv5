"""
Data Engine for Historical Stock Market Simulator
Uses internal Historical Truth Table for pre-1950 data
With fallback to sample data if needed
"""

from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os
import random
import time
import pandas as pd

# Import practice mode configuration and practice data
from practice_mode import PRACTICE_MODE
from practice_data import PRACTICE_DATA

if PRACTICE_MODE:
    TICKERS = PRACTICE_DATA['tickers']
    COMPANY_NAMES = PRACTICE_DATA['company_names']
    IPO_DATES = PRACTICE_DATA['ipo_dates']
else:
    TICKERS = ['^DJI', '^GSPC']
    COMPANY_NAMES = {
        '^DJI': 'Dow Jones Industrial Average',
        '^GSPC': 'S&P 500'
    }
    IPO_DATES = {
        '^DJI': '1900-01-01',
        '^GSPC': '1957-03-01'
    }

# Cache file for storing fetched data
CACHE_FILE = 'stock_data_cache.json'

# Fallback prices for Jan 1, 1928 (historical reference)
FALLBACK_PRICES_1928 = {
    '^DJI': 200.00,
    '^GSPC': 17.50
}

# Comprehensive Historical Truth Table for Dow Jones (^DJI) — 1928-2026
DOW_JONES_TABLE = {
    # 1928-1934: Roaring Twenties through Great Depression
    '1928-01-01': 200.00,      # Jan 1928 — Roaring Twenties Boom baseline
    '1928-12-01': 300.00,      # Dec 1928 — Aggressive late-year bull market run
    '1929-09-03': 381.17,      # Sept 3, 1929 — Absolute Pre-Crash Peak
    '1929-10-29': 230.00,      # Oct 29, 1929 — Black Tuesday
    '1929-11-01': 198.69,      # Nov 1929 — First massive post-crash trough
    '1930-04-01': 294.00,      # Apr 1930 — The "Dead Cat Bounce"
    '1930-12-01': 160.00,      # Dec 1930 — Systemic bank panics accelerate
    '1931-09-01': 110.00,      # Sept 1931 — UK abandons Gold Standard
    '1931-12-01': 75.00,       # Dec 1931 — Intense panic selling wave
    '1932-07-08': 41.22,       # July 8, 1932 — Absolute Great Depression Bottom
    '1932-09-01': 75.00,       # Sept 1932 — Initial relief bounce from dead lows
    '1933-02-01': 50.00,       # Feb 1933 — National Banking Holiday panics
    '1933-07-01': 108.00,      # July 1933 — FDR New Deal optimism / rally
    '1933-10-01': 85.00,       # Oct 1933 — Autumn economic stabilization
    '1934-02-01': 110.00,      # Feb 1934 — Late winter consolidation
    '1934-10-01': 95.00,       # Oct 1934 — Late year baseline stabilization
    # 1937-2026: WWII through Present Day
    '1937-03-01': 194.00,      # Mar 1937 — Pre-WWII Roosevelt Recession Peak
    '1938-03-01': 99.00,       # Mar 1938 — Roosevelt Recession Bottom
    '1946-05-01': 212.00,      # May 1946 — Immediate Post-WWII Victory Boom Peak
    '1949-06-01': 161.00,      # Jun 1949 — Post-war recession bottom
    '1953-01-01': 290.00,      # Jan 1953 — Eisenhower Post-Korean War Expansion
    '1959-12-01': 680.00,      # Dec 1959 — Fabulous Fifties Bull Market Peak
    '1966-02-01': 995.00,      # Feb 1966 — Mid-Sixties Economic Peak
    '1970-05-01': 631.00,      # May 1970 — Vietnam Era / Cambodian Campaign Crash Bottom
    '1973-01-01': 1051.00,     # Jan 1973 — Pre-Stagflation / Pre-Oil Shock Peak
    '1974-12-01': 577.00,      # Dec 1974 — Brutal OPEC Oil Embargo / Stagflation Trough
    '1982-08-01': 776.00,      # Aug 1982 — Volcker Interest Rate Volatility Bottom
    '1987-08-01': 2722.00,     # Aug 1987 — 1980s Mega-Bull Market Intermediary Peak
    '1987-10-19': 1738.00,     # Oct 19, 1987 — Black Monday
    '2000-01-01': 11720.00,    # Jan 2000 — Dot-Com Bubble Peak
    '2002-10-01': 7286.00,     # Oct 2002 — Dot-Com Bust & 9/11 Aftermath Bottom
    '2007-10-01': 14164.00,    # Oct 2007 — Pre-Great Recession Housing Bubble Peak
    '2009-03-01': 6547.00,     # Mar 2009 — Global Financial Crisis Meltdown Bottom
    '2020-02-01': 29551.00,    # Feb 2020 — Pre-Pandemic Modern Era High
    '2020-03-01': 18591.00,    # Mar 2020 — Flash COVID-19 Lockdowns Crash
    '2022-01-01': 36799.00,    # Jan 2022 — Post-Pandemic Hyper-Stimulus Peak
    '2022-10-01': 28725.00,    # Oct 2022 — Fed Aggressive Rate Hike Bottom
    '2024-01-01': 38150.00,    # Jan 2024 — AI Tech Wave Resurgence
    '2025-01-01': 42500.00,    # Jan 2025 — Extended Multi-Year Secular Bull Run
    '2026-05-01': 44300.00,    # May 2026 — Present Day Simulation Baseline
}

SP500_TABLE = {
    # 1928-1934: Pre-S&P 500 era (S&P 90 predecessor composite)
    '1928-01-01': 17.50,       # Jan 1928 — Roaring Twenties baseline
    '1928-12-01': 24.00,       # Dec 1928 — Late-year bull run
    '1929-09-03': 31.92,       # Sept 3, 1929 — Pre-Crash Peak
    '1929-10-29': 21.50,       # Oct 29, 1929 — Black Tuesday
    '1929-11-01': 17.60,       # Nov 1929 — Post-crash trough
    '1930-04-01': 25.50,       # Apr 1930 — Dead Cat Bounce
    '1930-12-01': 15.50,       # Dec 1930 — Bank panics / liquidations
    '1931-09-01': 10.50,       # Sept 1931 — UK abandons Gold Standard
    '1931-12-01': 8.00,        # Dec 1931 — Panic selling wave
    '1932-07-08': 4.40,        # July 8, 1932 — Great Depression Bottom
    '1932-09-01': 7.20,        # Sept 1932 — Relief bounce
    '1933-02-01': 5.50,        # Feb 1933 — Banking Holiday
    '1933-07-01': 12.20,       # July 1933 — New Deal optimism
    '1933-10-01': 9.10,        # Oct 1933 — Autumn stabilization
    '1934-02-01': 11.20,       # Feb 1934 — Consolidation
    '1934-10-01': 9.70,        # Oct 1934 — Baseline stabilization
    # 1937-2026
    '1937-03-01': 18.00,       # Mar 1937 — Pre-WWII Peak
    '1938-03-01': 9.00,        # Mar 1938 — Recession Bottom
    '1946-05-01': 19.00,       # May 1946 — Post-WWII Boom Peak
    '1949-06-01': 14.00,       # Jun 1949 — Post-war recession bottom
    '1953-01-01': 26.00,       # Jan 1953 — Eisenhower Expansion
    '1959-12-01': 60.00,       # Dec 1959 — Fabulous Fifties Peak
    '1966-02-01': 94.00,       # Feb 1966 — Mid-Sixties Peak
    '1970-05-01': 69.00,       # May 1970 — Vietnam Era Bottom
    '1973-01-01': 120.00,      # Jan 1973 — Pre-Stagflation Peak
    '1974-12-01': 62.00,       # Dec 1974 — OPEC Trough
    '1982-08-01': 102.00,      # Aug 1982 — Volcker Bottom
    '1987-08-01': 336.00,      # Aug 1987 — Mega-Bull Peak
    '1987-10-19': 224.00,      # Oct 19, 1987 — Black Monday
    '2000-01-01': 1528.00,     # Jan 2000 — Dot-Com Peak
    '2002-10-01': 776.00,      # Oct 2002 — Dot-Com Bust Bottom
    '2007-10-01': 1565.00,     # Oct 2007 — Pre-Great Recession Peak
    '2009-03-01': 676.00,      # Mar 2009 — GFC Bottom
    '2020-02-01': 3386.00,     # Feb 2020 — Pre-Pandemic High
    '2020-03-01': 2237.00,     # Mar 2020 — COVID Crash
    '2022-01-01': 4796.00,     # Jan 2022 — Post-Pandemic Peak
    '2022-10-01': 3577.00,     # Oct 2022 — Fed Hike Bottom
    '2024-01-01': 4890.00,     # Jan 2024 — AI Resurgence
    '2025-01-01': 5400.00,     # Jan 2025 — Secular Bull Run
    '2026-05-01': 5650.00,     # May 2026 — Present Day Baseline
}

# Master Truth Table (1929-2026) - MASTER_HISTORY (for backward compatibility)
MASTER_HISTORY = {
    '^DJI': DOW_JONES_TABLE,
    '^GSPC': SP500_TABLE
}

# Black Monday 1987-10-19 event
BLACK_MONDAY_DROPS = {
    '^DJI': 0.226,  # 22.6% drop
    '^GSPC': 0.204  # 20.4% drop
}

def lerp(start: float, end: float, t: float) -> float:
    """Linear interpolation between start and end values"""
    return start + (end - start) * t

def generate_sample_data():
    """Generate sample historical data for demonstration"""
    print("Generating sample data...")
    
    base_date = datetime(1920, 1, 1)
    end_date = datetime(2024, 12, 31)
    
    # Fallback prices for Jan 1, 1928 (historical reference)
    FALLBACK_PRICES_1928 = {
        '^DJI': 200.00,
        '^GSPC': 17.50
    }
    
    # Sample price data (simplified historical values)
    initial_prices = {
        '^DJI': 100.0,
        '^GSPC': 10.0
    }
    
    ipo_dates = IPO_DATES.copy()
    
    sample_data = {}
    
    for ticker in TICKERS:
        prices = {}
        ipo = datetime.strptime(ipo_dates[ticker], '%Y-%m-%d')
        price = initial_prices[ticker]
        current_date = base_date
        
        while current_date <= end_date:
            if current_date >= ipo:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # Use fallback price for Jan 1, 1928
                if date_str == '1928-01-01':
                    price = FALLBACK_PRICES_1928[ticker]
                    prices[date_str] = round(price, 2)
                elif current_date.weekday() < 5:
                    # Skip weekends for stocks
                    # Add realistic variation
                    year = current_date.year
                    
                    # VOLATILITY BOOST: Higher volatility during crisis years (1929-1932, 2008)
                    if 1929 <= year <= 1932 or year == 2008:
                        # +/- 5% per tick during crisis
                        change = (hash(date_str) % 1000 - 500) / 10000
                    else:
                        # Normal volatility +/- 5%
                        change = (hash(date_str) % 100 - 45) / 1000
                    
                    price = price * (1 + change)
                    # Ensure price doesn't go negative
                    if price < 0.01:
                        price = 0.01
                    prices[date_str] = round(price, 2)
            
            current_date += timedelta(days=1)
        
        sample_data[ticker] = {
            'prices': prices,
            'ipo_date': ipo_dates[ticker]
        }
        print(f"  Generated {len(prices)} days for {ticker}")
    
    return sample_data


class DataEngine:
    """Manages historical stock data fetching and retrieval"""
    
    def __init__(self):
        self.stock_data: Dict[str, Dict[str, float]] = {}
        self.ipo_dates: Dict[str, str] = {}
        self.sorted_price_dates: Dict[str, list] = {}
        
        if PRACTICE_MODE:
            self._load_practice_data()
        else:
            self._load_or_fetch_data()
        self._index_price_dates()
    
    def _load_practice_data(self):
        """Load practice mode data"""
        print("Loading practice mode data...")
        self.stock_data = PRACTICE_DATA['prices']
        self.ipo_dates = PRACTICE_DATA['ipo_dates']
        print(f"Loaded practice data for {len(self.stock_data)} ticker(s)")
    
    def _load_or_fetch_data(self):
        """Load cached data or generate from Monthly Historical Truth Table"""
        # Force delete stock_data_cache.json for this refactor
        if os.path.exists(CACHE_FILE):
            print("Force deleting stock_data_cache.json for v4.8 refactor...")
            os.remove(CACHE_FILE)

        # Version-based cache invalidation
        CACHE_VERSION_FILE = 'cache_version.txt'
        APP_VERSION = '5.1'  # Hard-coded to avoid circular import

        current_version = APP_VERSION
        cached_version = None

        if os.path.exists(CACHE_VERSION_FILE):
            with open(CACHE_VERSION_FILE, 'r') as f:
                cached_version = f.read().strip()

        # Clear cache if version mismatch
        if cached_version != current_version:
            print(f"Cache version mismatch (cached: {cached_version}, current: {current_version}), clearing cache...")
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
            with open(CACHE_VERSION_FILE, 'w') as f:
                f.write(current_version)

        print("Loading stock data from Monthly Historical Truth Table...")
        self._fetch_all_data()

        # If no data was fetched, generate sample data
        if not self.stock_data:
            print("Generating sample data...")
            self._generate_sample_data()

        self._save_cache()

    def reload_data(self):
        """Reload historical or practice data when mode changes."""
        from practice_mode import PRACTICE_MODE as practice_flag
        global TICKERS, COMPANY_NAMES, IPO_DATES

        if practice_flag:
            TICKERS = PRACTICE_DATA['tickers']
            COMPANY_NAMES = PRACTICE_DATA['company_names']
            IPO_DATES = PRACTICE_DATA['ipo_dates']
            self._load_practice_data()
        else:
            TICKERS = ['^DJI', '^GSPC']
            COMPANY_NAMES = {
                '^DJI': 'Dow Jones Industrial Average',
                '^GSPC': 'S&P 500'
            }
            IPO_DATES = {
                '^DJI': '1900-01-01',
                '^GSPC': '1957-03-01'
            }
            self._load_or_fetch_data()
        self._index_price_dates()

    def _index_price_dates(self):
        self.sorted_price_dates = {
            ticker: sorted(prices.keys())
            for ticker, prices in self.stock_data.items()
        }

    def _load_cache(self):
        """Load data from cache file"""
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                self.stock_data = data.get('stock_data', {})
                self.ipo_dates = data.get('ipo_dates', {})
            print(f"Loaded data for {len(self.stock_data)} tickers")
        except Exception as e:
            print(f"Error loading cache: {e}")
            self.stock_data = {}
            self.ipo_dates = {}
    
    def _save_cache(self):
        """Save data to cache file"""
        try:
            data = {
                'stock_data': self.stock_data,
                'ipo_dates': self.ipo_dates
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(data, f)
            print("Stock data cached successfully")
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def _fetch_all_data(self):
        """Fetch historical data for all tickers using Historical Truth Table"""
        for ticker in TICKERS:
            self._fetch_ticker_data(ticker)

    def _fetch_ticker_data(self, ticker: str):
        """Fetch historical data for a single ticker using MASTER_HISTORY"""
        try:
            print(f"Loading MASTER_HISTORY for {ticker}...")

            # For DJI, use MASTER_HISTORY directly - save to stock_data to stop initialization loop
            if ticker == '^DJI':
                benchmarks = MASTER_HISTORY.get('^DJI', {})
                print(f"  Loaded {len(benchmarks)} historical benchmarks for DJI")
                self.ipo_dates[ticker] = IPO_DATES.get(ticker, '1928-01-01')
                # Save to stock_data to stop initialization loop
                self.stock_data[ticker] = benchmarks
                self._initialized = True
                return

            # For other tickers, use sample data
            print(f"  Using sample data for {ticker}")
            sample = generate_sample_data()
            if ticker in sample:
                self.stock_data[ticker] = sample[ticker]['prices']
                self.ipo_dates[ticker] = sample[ticker]['ipo_date']
                print(f"  {ticker}: {len(sample[ticker]['prices'])} days, IPO: {sample[ticker]['ipo_date']}")
                self._initialized = True
                return

        except Exception as e:
            print(f"  Error generating data for {ticker}: {e}")
    
    def _fill_missing_dates(self, ticker: str, prices: Dict[str, float]):
        """Fill in missing dates between 1928 and fetched data range with sample data"""
        if not prices:
            return
        
        # Get the date range
        sorted_dates = sorted(prices.keys())
        first_date = sorted_dates[0]
        last_date = sorted_dates[-1]
        
        # Only fill if we have a gap between 1928 and the fetched data
        if first_date > '1928-01-01' and ticker in FALLBACK_PRICES_1928:
            # Start from the fallback price
            current_price = FALLBACK_PRICES_1928[ticker]
            
            # Calculate target price (first fetched price)
            target_price = prices[first_date]
            
            # Generate daily prices from 1928 to first fetched date
            start = datetime.strptime('1928-01-01', '%Y-%m-%d')
            end = datetime.strptime(first_date, '%Y-%m-%d')
            
            total_days = (end - start).days
            if total_days <= 0:
                return
            
            # Calculate daily growth rate to reach target
            daily_growth = (target_price / current_price) ** (1 / total_days) - 1
            
            current = start
            while current < end:
                date_str = current.strftime('%Y-%m-%d')
                
                if date_str not in prices:
                    year = current.year
                    days_from_start = (current - start).days
                    
                    # VOLATILITY BOOST: Higher volatility during crisis years (1929-1932, 2008)
                    if 1929 <= year <= 1932 or year == 2008:
                        # +/- 2% per day during crisis
                        change = (hash(date_str) % 100 - 50) / 2500
                    else:
                        # Normal volatility +/- 0.5%
                        change = (hash(date_str) % 100 - 50) / 10000
                    
                    # Apply growth + volatility
                    current_price = current_price * (1 + daily_growth + change)
                    if current_price < 0.01:
                        current_price = 0.01
                    prices[date_str] = round(current_price, 2)
                
                current += timedelta(days=1)
            
            self.stock_data[ticker] = prices
    
    def get_price(self, ticker: str, date: str) -> Optional[float]:
        try:
            # Use MASTER_HISTORY for both DJI and GSPC - all dates
            if ticker in MASTER_HISTORY:
                benchmarks = MASTER_HISTORY.get(ticker, {})
                sorted_benchmarks = sorted(benchmarks.items(), key=lambda x: x[0])

                # Find the two closest benchmarks for interpolation
                prev_date = None
                prev_value = None
                next_date = None
                next_value = None

                for benchmark_date, benchmark_value in sorted_benchmarks:
                    if date <= benchmark_date:
                        next_date = benchmark_date
                        next_value = benchmark_value
                        break
                    prev_date = benchmark_date
                    prev_value = benchmark_value

                # If date is exactly a benchmark, return that value
                if date == next_date:
                    return next_value

                # Apply Linear Interpolation between benchmarks (clean baseline, no smoothing)
                if prev_date and next_date:
                    prev_dt = datetime.strptime(prev_date, '%Y-%m-%d')
                    next_dt = datetime.strptime(next_date, '%Y-%m-%d')
                    current_dt = datetime.strptime(date, '%Y-%m-%d')
                    total_days = (next_dt - prev_dt).days
                    elapsed_days = (current_dt - prev_dt).days
                    t = elapsed_days / total_days if total_days > 0 else 0
                    base_price = lerp(prev_value, next_value, t)
                    return round(max(base_price, 0.01), 2)
                elif prev_date:
                    # Past last milestone: flat horizontal drift baseline
                    return round(max(prev_value, 0.01), 2)
                elif next_date:
                    # Before first milestone
                    return round(max(next_value, 0.01), 2)
                else:
                    # No benchmarks, use fallback
                    return round(max(FALLBACK_PRICES_1928.get(ticker, 150.00), 0.01), 2)

            # Get base price from stock data for dates >= 1950
            if ticker not in self.stock_data:
                return None

            ipo_date = self.ipo_dates.get(ticker)
            if ipo_date and date < ipo_date:
                return None

            if date in self.stock_data[ticker]:
                base_price = self.stock_data[ticker][date]
            else:
                base_price = self._find_closest_price(ticker, date)

            if base_price is None:
                return None

            # Apply Black Monday 1987-10-19 drop
            if date == '1987-10-19' and ticker in BLACK_MONDAY_DROPS:
                drop_percentage = BLACK_MONDAY_DROPS[ticker]
                return round(base_price * (1 - drop_percentage), 2)

            return base_price
        except Exception as e:
            print(f"ERROR in get_price for {ticker} on {date}: {e}")
            return None
    
    def _find_closest_price(self, ticker: str, target_date: str) -> Optional[float]:
        """Find the closest trading day price before or on the target date"""
        prices = self.stock_data.get(ticker, {})
        if not prices:
            return None
        
        sorted_dates = self.sorted_price_dates.get(ticker)
        if not sorted_dates:
            return None

        index = bisect_right(sorted_dates, target_date) - 1
        if index < 0:
            return None

        return prices[sorted_dates[index]]
    
    def is_available(self, ticker: str, date: str) -> bool:
        """Check if a stock is available for trading on a given date"""
        ipo_date = self.ipo_dates.get(ticker)
        if not ipo_date:
            return False
        return date >= ipo_date
    
    def get_ipo_date(self, ticker: str) -> Optional[str]:
        """Get the IPO date for a ticker"""
        return self.ipo_dates.get(ticker)
    
    def get_all_prices(self, date: str) -> Dict[str, float]:
        """Get all stock prices for a given date"""
        prices = {}
        for ticker in TICKERS:
            price = self.get_price(ticker, date)
            if price is not None:
                prices[ticker] = price
        return prices
    
    def get_company_name(self, ticker: str) -> str:
        """Get the company name for a ticker"""
        return COMPANY_NAMES.get(ticker, ticker)
    
    def get_tickers(self) -> list:
        """Get list of all tickers"""
        return TICKERS.copy()
    
    def get_available_tickers(self, date: str) -> list:
        """Get list of tickers available for trading on a given date"""
        available = []
        for ticker in TICKERS:
            if self.is_available(ticker, date):
                available.append(ticker)
        return available
    
    def get_date_range(self) -> tuple:
        """Get the earliest and latest dates available"""
        baseline_start = '1920-01-01'
        all_dates = set()
        for prices in self.stock_data.values():
            all_dates.update(prices.keys())

        if not all_dates:
            return (baseline_start, '2024-12-31')

        return (baseline_start, max(all_dates))

    def get_historical_prices(self, ticker: str, start_date: str, end_date: str, num_points: int = 100) -> Dict[str, float]:
        """Get historical prices for a ticker between start_date and end_date"""
        if ticker not in self.stock_data:
            return {}

        prices = {}
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        # Calculate the step size to get num_points
        total_days = (end - start).days
        if total_days <= 0:
            return {}
        step_size = max(1, total_days // num_points)

        current = start
        count = 0
        while current <= end and count < num_points:
            date_str = current.strftime('%Y-%m-%d')
            price = self.get_price(ticker, date_str)
            if price is not None:
                prices[date_str] = price
                count += 1
            current += timedelta(days=step_size)

        return prices


# Global data engine instance
data_engine = DataEngine()


# Global data engine instance
data_engine = DataEngine()