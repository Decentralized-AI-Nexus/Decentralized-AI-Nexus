# ======================================================================================================================
#
# ======================================================================================================================

import io
from datetime import datetime

import backtrader as bt
import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

# ======================================================================================================================

# ======================================================================================================================


Amberdata_API_KEY = "YOUR_API_KEY"


icap = 100000


PercSize = 100


PercTrail = 0.40


start_date = "2015-01-20"
end_date = "2020-05-09"


# ======================================================================================================================

# ======================================================================================================================

class CustomPandas(bt.feeds.PandasData):
    # Add a 'stf' line to the inherited ones from the base class
    lines = ("stf",)

    params = (("stf", 8),)



def amberdata(url, queryString, apiKey):
    try:
        headers = {"x-api-key": apiKey}
        response = requests.request("GET", url, headers=headers, params=queryString)
        return response.text
    except Exception as e:
        raise e



def amberdata_ohlcv(exchange, symbol, startDate, endDate):
    format = "%Y-%m-%dT%H:%M:%S"
    startTimestamp = datetime.strptime(startDate, "%Y-%m-%d")
    endTimestamp = datetime.strptime(endDate, "%Y-%m-%d")

    current = startTimestamp
    next = current
    fields = "timestamp,open,high,low,close,volume"
    payload = fields
    while current < endTimestamp:
        next += relativedelta(years=1)
        if next > endTimestamp:
            next = endTimestamp
        print("Retrieving OHLCV between", current, " and ", next)
        result = amberdata(
            "https://web3api.io/api/v2/market/ohlcv/" + symbol + "/historical",
            {
                "exchange": exchange,
                "timeInterval": "days",
                "timeFormat": "iso",
                "format": "raw_csv",
                "fields": fields,
                "startDate": current.strftime(format),
                "endDate": next.strftime(format),
            },
            Amberdata_API_KEY,
        )
        payload += "\n" + result
        current = next

    return payload



def amberdata_stf(symbol, startDate, endDate):
    print("Retrieving STF between", startDate, " and ", endDate)
    return amberdata(
        "https://web3api.io/api/v2/market/metrics/"
        + symbol
        + "/historical/stock-to-flow",
        {
            "format": "csv",
            "timeFrame": "day",
            "startDate": startDate,
            "endDate": endDate,
        },
        Amberdata_API_KEY,
    )


def to_pandas(csv):
    return pd.read_csv(io.StringIO(csv), index_col="timestamp", parse_dates=True)


# ======================================================================================================================
# 策略
# ======================================================================================================================


class Strategy(bt.Strategy):
    params = (
        ("macd1", 12),
        ("macd2", 26),
        ("macdsig", 9),
        ("trailpercent", PercTrail),
        ("smaperiod", 30),
        ("dirperiod", 10),
    )

    def notify_order(self, order):
        if order.status == order.Completed:
            pass

        if not order.alive():
            self.order = None  # No pending orders

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data,
            period_me1=self.p.macd1,
            period_me2=self.p.macd2,
            period_signal=self.p.macdsig,
        )

        # Cross of macd.macd and macd.signal
        self.mcross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

        self.sma = bt.indicators.SMA(self.data, period=self.p.smaperiod)

        self.smadir = self.sma - self.sma(-self.p.dirperiod)

    def start(self):
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:

            if (
                self.mcross[0] > 0.0
                and self.smadir < 0.0
                and self.data.close < self.data.stf
            ):
                self.order = self.buy()

        elif self.order is None:

            self.order = self.sell(
                exectype=bt.Order.StopTrail, trailpercent=self.p.trailpercent
            )


# ======================================================================================================================

# ======================================================================================================================


cerebro = bt.Cerebro(stdstats=False)
cerebro.broker.setcash(icap)


cerebro.addsizer(bt.sizers.PercentSizer, percents=PercSize)

# Add our strategy
cerebro.addstrategy(Strategy)


btc = to_pandas(amberdata_ohlcv("gdax", "btc_usd", start_date, end_date))
btc.to_csv("btc_new.csv")

btc_stf = to_pandas(amberdata_stf("btc", start_date, end_date))

btc["stf"] = btc_stf["price"]


cerebro.adddata(CustomPandas(dataname=btc, openinterest=None, stf="stf"))


backtest = cerebro.run()
