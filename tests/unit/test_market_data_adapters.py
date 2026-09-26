"""Unit tests for multi-exchange market data adapters and aggregator."""

import unittest
from unittest.mock import patch

from market_data import (
    BinanceFuturesAdapter,
    BybitLinearAdapter,
    MarketDataAdapter,
    MexcFuturesAdapter,
    MultiExchangeAggregator,
    OkxSwapAdapter,
    create_market_data_adapter,
    safe_float,
)


class MarketDataAdaptersTests(unittest.TestCase):
    def test_factory_creates_expected_adapter_types(self):
        mexc = create_market_data_adapter("mexc_futures")
        self.assertIsInstance(mexc, MexcFuturesAdapter)
        self.assertEqual(mexc.exchange_name, "MEXC")

        binance = create_market_data_adapter("binance_futures")
        self.assertIsInstance(binance, BinanceFuturesAdapter)
        self.assertEqual(binance.exchange_name, "BINANCE")

        bybit = create_market_data_adapter("bybit_linear")
        self.assertIsInstance(bybit, BybitLinearAdapter)
        self.assertEqual(bybit.exchange_name, "BYBIT")

        okx = create_market_data_adapter("okx_swap")
        self.assertIsInstance(okx, OkxSwapAdapter)
        self.assertEqual(okx.exchange_name, "OKX")

        multi = create_market_data_adapter("multi_exchange")
        self.assertIsInstance(multi, MultiExchangeAggregator)
        self.assertEqual(len(multi.adapters), 4)

    def test_factory_rejects_unknown_source(self):
        with self.assertRaises(ValueError) as ctx:
            create_market_data_adapter("unknown_dex")
        self.assertIn("Unsupported market data source", str(ctx.exception))

    def test_binance_canonical_signal(self):
        adapter = BinanceFuturesAdapter()
        prem = {
            "symbol": "SOLUSDT",
            "markPrice": "150.25",
            "lastFundingRate": "-0.0055",
            "nextFundingTime": 1740000000000,
        }
        ticker_24h = {
            "symbol": "SOLUSDT",
            "lastPrice": "150.25",
            "quoteVolume": "500000000.0",
            "highPrice": "160.0",
        }
        sig = adapter.canonical_signal(prem, ticker_24h=ticker_24h)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["exchange"], "BINANCE")
        self.assertEqual(sig["symbol"], "SOL")
        self.assertEqual(sig["rawSymbol"], "SOLUSDT")
        self.assertEqual(sig["fundingRate"], -0.0055)
        self.assertEqual(sig["price"], 150.25)
        self.assertGreater(sig["volume24h"], 0)
        self.assertGreater(sig["openInterest"], 0)

    def test_bybit_canonical_signal(self):
        adapter = BybitLinearAdapter()
        ticker = {
            "symbol": "DOGEUSDT",
            "lastPrice": "0.185",
            "fundingRate": "-0.0042",
            "openInterestValue": "150000000.0",
            "turnover24h": "350000000.0",
            "highPrice24h": "0.20",
        }
        sig = adapter.canonical_signal(ticker)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["exchange"], "BYBIT")
        self.assertEqual(sig["symbol"], "DOGE")
        self.assertEqual(sig["rawSymbol"], "DOGEUSDT")
        self.assertEqual(sig["fundingRate"], -0.0042)
        self.assertEqual(sig["price"], 0.185)
        self.assertEqual(sig["openInterest"], 150000000.0)
        self.assertEqual(sig["volume24h"], 350000000.0)

    def test_okx_canonical_signal(self):
        adapter = OkxSwapAdapter()
        ticker = {
            "instId": "PEPE-USDT-SWAP",
            "last": "0.0000095",
            "volCcy24h": "5000000000.0",
            "high24h": "0.000011",
        }
        oi_item = {
            "instId": "PEPE-USDT-SWAP",
            "oiUsd": "45000000.0",
        }
        sig = adapter.canonical_signal(ticker, funding_rate=-0.0038, oi_item=oi_item)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["exchange"], "OKX")
        self.assertEqual(sig["symbol"], "PEPE")
        self.assertEqual(sig["rawSymbol"], "PEPE-USDT-SWAP")
        self.assertEqual(sig["fundingRate"], -0.0038)
        self.assertEqual(sig["price"], 0.0000095)
        self.assertEqual(sig["openInterest"], 45000000.0)

    def test_mexc_canonical_signal(self):
        adapter = MexcFuturesAdapter(cache_dir="data/cache")
        ticker = {
            "symbol": "BTC_USDT",
            "lastPrice": "84000.0",
            "fundingRate": "-0.0030",
            "holdVol": "1000",
            "amount24": "80000000.0",
        }
        sig = adapter.canonical_signal(ticker)
        self.assertIsNotNone(sig)
        self.assertEqual(sig["exchange"], "MEXC")
        self.assertEqual(sig["symbol"], "BTC")
        self.assertEqual(sig["fundingRate"], -0.0030)

    def test_multi_exchange_aggregator_merges_and_ranks_globally(self):
        class MockAdapter(MarketDataAdapter):
            def __init__(self, source_id, exchange_name, anomalies):
                self.source_id = source_id
                self.exchange_name = exchange_name
                self.anomalies = anomalies

            def scan_anomalies(self):
                return self.anomalies

        mock_binance = MockAdapter("binance", "BINANCE", [
            {"symbol": "SOL", "exchange": "BINANCE", "fundingRate": -0.0040},
            {"symbol": "AVAX", "exchange": "BINANCE", "fundingRate": -0.0010},
        ])
        mock_bybit = MockAdapter("bybit", "BYBIT", [
            {"symbol": "PEPE", "exchange": "BYBIT", "fundingRate": -0.0080},
        ])
        mock_mexc = MockAdapter("mexc", "MEXC", [
            {"symbol": "DOGE", "exchange": "MEXC", "fundingRate": -0.0060},
        ])

        aggregator = MultiExchangeAggregator(
            adapters=[mock_binance, mock_bybit, mock_mexc],
            anomaly_limit=10,
        )
        ranked = aggregator.scan_anomalies()

        self.assertEqual(len(ranked), 4)
        # Global ranking: most negative funding rate first (-0.0080, -0.0060, -0.0040, -0.0010)
        self.assertEqual(ranked[0]["symbol"], "PEPE")
        self.assertEqual(ranked[0]["exchange"], "BYBIT")
        self.assertEqual(ranked[0]["fundingRate"], -0.0080)

        self.assertEqual(ranked[1]["symbol"], "DOGE")
        self.assertEqual(ranked[1]["exchange"], "MEXC")

        self.assertEqual(ranked[2]["symbol"], "SOL")
        self.assertEqual(ranked[2]["exchange"], "BINANCE")

    def test_multi_exchange_token_grouping_and_spread(self):
        class MockAdapter:
            def __init__(self, source_id, exchange_name, anomalies):
                self.source_id = source_id
                self.exchange_name = exchange_name
                self.anomalies = anomalies

            def scan_anomalies(self):
                return self.anomalies

        # SOL appears on 3 different exchanges with different funding rates
        mock_binance = MockAdapter("binance", "BINANCE", [
            {"symbol": "SOL", "exchange": "BINANCE", "fundingRate": -0.0050, "volume24h": 1000},
        ])
        mock_bybit = MockAdapter("bybit", "BYBIT", [
            {"symbol": "SOL", "exchange": "BYBIT", "fundingRate": -0.0090, "volume24h": 800},
            {"symbol": "BTC", "exchange": "BYBIT", "fundingRate": -0.0020, "volume24h": 5000},
        ])
        mock_mexc = MockAdapter("mexc", "MEXC", [
            {"symbol": "SOL", "exchange": "MEXC", "fundingRate": -0.0030, "volume24h": 300},
        ])

        aggregator = MultiExchangeAggregator(
            adapters=[mock_binance, mock_bybit, mock_mexc],
            anomaly_limit=10,
        )
        ranked = aggregator.scan_anomalies()

        # SOL should be consolidated into 1 entry, not 3 separate entries!
        self.assertEqual(len(ranked), 2)  # SOL and BTC
        sol_item = ranked[0]
        self.assertEqual(sol_item["symbol"], "SOL")
        # Primary is BYBIT because it has the most negative funding rate (-0.0090)
        self.assertEqual(sol_item["exchange"], "BYBIT")
        self.assertEqual(sol_item["fundingRate"], -0.0090)
        # Should record all 3 venues
        self.assertEqual(sol_item["venues_count"], 3)
        venue_exchanges = [v["exchange"] for v in sol_item["venues"]]
        self.assertIn("BYBIT", venue_exchanges)
        self.assertIn("BINANCE", venue_exchanges)
        self.assertIn("MEXC", venue_exchanges)
        # Spread: |-0.0030 - (-0.0090)| = 0.0060
        self.assertAlmostEqual(sol_item["funding_spread"], 0.0060, places=4)


if __name__ == "__main__":
    unittest.main()
