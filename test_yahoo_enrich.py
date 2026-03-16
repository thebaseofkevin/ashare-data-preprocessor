"""Test code for yahoo_enrich.py"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import pandas as pd

# Add the current directory to sys.path to import yahoo_enrich
sys.path.insert(0, os.path.dirname(__file__))

from yahoo_enrich import _baostock_to_yahoo, fetch_yahoo

class TestYahooEnrich(unittest.TestCase):

    def test_baostock_to_yahoo_sh(self):
        """Test conversion for Shanghai stocks."""
        self.assertEqual(_baostock_to_yahoo("sh.600000"), "600000.SS")

    def test_baostock_to_yahoo_sz(self):
        """Test conversion for Shenzhen stocks."""
        self.assertEqual(_baostock_to_yahoo("sz.000001"), "000001.SZ")

    def test_baostock_to_yahoo_other(self):
        """Test conversion for other codes."""
        self.assertEqual(_baostock_to_yahoo("other"), "other")

    @patch('yahoo_enrich.yf')
    def test_fetch_yahoo_with_data(self, mock_yf):
        """Test fetch_yahoo when yfinance returns data."""
        # Mock the Ticker
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {
            "website": "http://example.com",
            "sharesOutstanding": 1000000,
            "marketCap": 200000000,
            "trailingPE": 15.5,
            "priceToBook": 2.0,
            "returnOnEquity": 0.1,
            "trailingEps": 1.5,
            "bookValue": 10.0,
            "totalCash": 500000,
            "currentPrice": 12.30
        }
        mock_ticker.fast_info = {"previous_close": 12.30}
        mock_ticker.balance_sheet = pd.DataFrame(
            {0: [300000, 200000]},
            index=["Cash And Cash Equivalents", "Short Term Debt"],
        )
        mock_ticker.financials = pd.DataFrame(
            {0: [100000, 500000, 50000, 70000, 8000]},
            index=[
                "Gross Profit",
                "Total Revenue",
                "Net Income Continuous Operations",
                "Operating Expense",
                "Research And Development",
            ],
        )
        mock_ticker.cashflow = pd.DataFrame(
            {0: [150000, -50000, 25000]},
            index=[
                "Operating Cash Flow",
                "Capital Expenditures",
                "Financing Cash Flow",
            ],
        )

        mock_yf.Ticker.return_value = mock_ticker

        data, err = fetch_yahoo("sh.600000")
        self.assertIsNone(err)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["website"], "http://example.com")
        self.assertEqual(data["total_share"], 1000000)
        self.assertEqual(data["market_cap"], 200000000)
        self.assertEqual(data["price"], 12.30)
        self.assertEqual(data["pe"], 15.5)
        self.assertEqual(data["pb"], 2.0)
        self.assertEqual(data["roe"], 0.1)
        self.assertEqual(data["eps"], 1.5)
        self.assertEqual(data["bps"], 10.0)
        self.assertEqual(data["cash"], 300000)
        self.assertEqual(data["short_term_borrowing"], 200000)
        self.assertEqual(data["gross_profit_margin"], "20%")  # 100000 / 500000
        self.assertEqual(data["net_profit"], 50000)
        self.assertEqual(data["operating_cash_flow"], 150000)
        self.assertEqual(data["investment_cash_flow"], -50000)
        self.assertEqual(data["financing_cash_flow"], 25000)
        self.assertEqual(data["operating_expense"], 70000)
        self.assertEqual(data["research_and_development"], 8000)

    @patch('yahoo_enrich.yf', None)
    def test_fetch_yahoo_no_yf(self):
        """Test fetch_yahoo when yfinance is not installed."""
        data, err = fetch_yahoo("sh.600000")
        self.assertEqual(data, {})
        self.assertEqual(err, "yfinance not installed")

    @patch('yahoo_enrich.yf')
    def test_fetch_yahoo_exception(self, mock_yf):
        """Test fetch_yahoo when an exception occurs."""
        mock_yf.Ticker.side_effect = Exception("Network error")
        data, err = fetch_yahoo("sh.600000")
        self.assertEqual(data, {})
        self.assertEqual(err, "Network error")

    @patch('yahoo_enrich.yf')
    def test_financing_cash_flow_alias(self, mock_yf):
        """Test financing cash flow label compatibility."""
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {}
        mock_ticker.fast_info = {}
        mock_ticker.balance_sheet = pd.DataFrame()
        mock_ticker.financials = pd.DataFrame()
        mock_ticker.cashflow = pd.DataFrame(
            {0: [12345]},
            index=["Total Cash From Financing Activities"],
        )
        mock_yf.Ticker.return_value = mock_ticker

        data, err = fetch_yahoo("sh.600000")
        self.assertIsNone(err)
        self.assertEqual(data["financing_cash_flow"], 12345)

if __name__ == '__main__':
    unittest.main()
