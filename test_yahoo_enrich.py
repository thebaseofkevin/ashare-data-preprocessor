"""Test code for yahoo_enrich.py"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

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
        mock_ticker.info = {
            "website": "http://example.com",
            "sharesOutstanding": 1000000,
            "trailingPE": 15.5,
            "priceToBook": 2.0,
            "returnOnEquity": 0.1,
            "trailingEps": 1.5,
            "bookValue": 10.0,
            "totalCash": 500000
        }
        mock_ticker.balance_sheet = MagicMock()
        mock_ticker.balance_sheet.empty = False
        mock_ticker.balance_sheet.index = ["Short Term Debt"]
        debt_mock = MagicMock()
        debt_mock.iloc = [200000]
        mock_ticker.balance_sheet.loc = MagicMock()
        mock_ticker.balance_sheet.loc.__getitem__ = lambda self, key: {"Short Term Debt": debt_mock}.get(key, MagicMock())

        mock_ticker.financials = MagicMock()
        mock_ticker.financials.empty = False
        mock_ticker.financials.index = ["Gross Profit", "Total Revenue", "Net Income"]

        # Create separate mocks for each loc access
        gross_mock = MagicMock()
        gross_mock.iloc = [100000]
        revenue_mock = MagicMock()
        revenue_mock.iloc = [500000]
        net_mock = MagicMock()
        net_mock.iloc = [50000]

        mock_ticker.financials.loc = MagicMock()
        mock_ticker.financials.loc.__getitem__ = lambda self, key: {
            "Gross Profit": gross_mock,
            "Total Revenue": revenue_mock,
            "Net Income": net_mock
        }.get(key, MagicMock())

        mock_ticker.cashflow = MagicMock()
        mock_ticker.cashflow.empty = False
        mock_ticker.cashflow.index = ["Operating Cash Flow", "Capital Expenditures"]
        op_mock = MagicMock()
        op_mock.iloc = [150000]
        cap_mock = MagicMock()
        cap_mock.iloc = [-50000]
        mock_ticker.cashflow.loc = MagicMock()
        mock_ticker.cashflow.loc.__getitem__ = lambda self, key: {
            "Operating Cash Flow": op_mock,
            "Capital Expenditures": cap_mock
        }.get(key, MagicMock())

        mock_yf.Ticker.return_value = mock_ticker

        result = fetch_yahoo("sh.600000")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["website"], "http://example.com")
        self.assertEqual(result["total_share"], 1000000)
        self.assertEqual(result["pe"], 15.5)
        self.assertEqual(result["pb"], 2.0)
        self.assertEqual(result["roe"], 0.1)
        self.assertEqual(result["eps"], 1.5)
        self.assertEqual(result["bps"], 10.0)
        self.assertEqual(result["cash"], 500000)
        self.assertEqual(result["short_term_loan"], 200000)
        self.assertEqual(result["short_term_borrowing"], 200000)
        self.assertEqual(result["gross_profit_margin"], 0.2)  # 100000 / 500000
        self.assertEqual(result["net_profit"], 50000)
        self.assertEqual(result["operating_cash_flow"], 150000)
        self.assertEqual(result["investment_cash_flow"], -50000)

    @patch('yahoo_enrich.yf', None)
    def test_fetch_yahoo_no_yf(self):
        """Test fetch_yahoo when yfinance is not installed."""
        result = fetch_yahoo("sh.600000")
        self.assertEqual(result, {})

    @patch('yahoo_enrich.yf')
    def test_fetch_yahoo_exception(self, mock_yf):
        """Test fetch_yahoo when an exception occurs."""
        mock_yf.Ticker.side_effect = Exception("Network error")
        result = fetch_yahoo("sh.600000")
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()