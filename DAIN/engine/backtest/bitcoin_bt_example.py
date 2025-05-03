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

def xirrcal(cftable, trades, date, startdate=None, guess=0.01):
    """
    calculate the xirr rate

    :param cftable: cftable (pd.Dateframe) with date and cash column
    :param trades: list [trade1, ...], every item is an trade object,
        whose shares would be sold out virtually
    :param date: string of date or datetime object,
        the date when virtually all holding positions being sold
    :param guess: floating number, a guess at the xirr rate solution to be used
        as a starting point for the numerical solution
    :returns: the IRR as a single floating number
    """
    date = convert_date(date)
    partcftb = cftable[cftable["date"] <= date]
    if len(partcftb) == 0:
        return 0
    if not startdate:
        cashflow = [(row["date"], row["cash"]) for i, row in partcftb.iterrows()]
    else:
        if not isinstance(startdate, dt.datetime):
            startdate = dt.datetime.strptime(
                startdate.replace("-", "").replace("/", ""), "%Y%m%d"
            )
        start_cash = 0
        for fund in trades:
            start_cash += fund.briefdailyreport(startdate).get("currentvalue", 0)
        cashflow = [(startdate, -start_cash)]
        partcftb = partcftb[partcftb["date"] > startdate]
        cashflow.extend([(row["date"], row["cash"]) for i, row in partcftb.iterrows()])
    rede = 0
    for fund in trades:
        if not isinstance(fund, itrade):
            partremtb = fund.remtable[fund.remtable["date"] <= date]
            if len(partremtb) > 0:
                rem = partremtb.iloc[-1]["rem"]
            else:
                rem = []
            rede += fund.aim.shuhui(
                fund.briefdailyreport(date).get("currentshare", 0), date, rem
            )[1]
        else:  
            rede += fund.briefdailyreport(date).get("currentvalue", 0)
    cashflow.append((date, rede))
    return xirr(cashflow, guess)


def bottleneck(cftable):
    """
    find the max total input in the history given cftable with cash column

    :param cftable: pd.DataFrame of cftable
    """
    if len(cftable) == 0:
        return 0
    # cftable = cftable.reset_index(drop=True) # unnecessary as iloc use natural rows instead of default index
    inputl = [-sum(cftable.iloc[:i].cash) for i in range(1, len(cftable) + 1)]
    return myround(max(inputl))


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
