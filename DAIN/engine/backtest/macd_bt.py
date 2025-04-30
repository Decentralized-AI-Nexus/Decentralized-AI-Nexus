import backtrader as bt
import pandas as pd
import tushare as ts


class MyStrategy(bt.Strategy):
    params = (
        ("fast", 5),
        ("slow", 20),
    )

    def __init__(self):
        self.fast_moving_average = bt.indicators.SMA(
            self.data.close,
            period=self.params.fast,
            plotname="5 day moving average",
        )
        self.slow_moving_average = bt.indicators.SMA(
            self.data.close,
            period=self.params.slow,
            plotname="20 day moving average",
        )
        self.crossover = bt.indicators.CrossOver(
            self.fast_moving_average, self.slow_moving_average
        )
    def correlation_table(self, end=yesterdayobj()):
        """
        give the correlation coefficient amongst referenced funds and indexes

        :param end: string or object of date, the end date of the line
        :returns: pandas DataFrame, with correlation coefficient as elements
        """
        partprice = self.totprice[self.totprice["date"] <= end]
        covtable = partprice.iloc[:, 1:].pct_change().corr()
        return covtable

    def v_correlation(self, end=yesterdayobj(), vopts=None, rendered=True):
        """
       Visualization of the correlation of the net value of each fund

        :param end: string or object of date, the end date of the line
        :returns: pyecharts.charts.Heatmap.render_notebook object
        """
        ctable = self.correlation_table(end)
        x_axis = list(ctable.columns)
        data = [
            [i, j, ctable.iloc[i, j]]
            for i in range(len(ctable))
            for j in range(len(ctable))
        ]
        heatmap = HeatMap()
        heatmap.add_xaxis(x_axis)
        heatmap.add_yaxis(series_name="correlation", yaxis_data=x_axis, value=data)
        if vopts is None:
            vopts = heatmap_opts
        heatmap.set_global_opts(**vopts)
        if rendered:
            return heatmap.render_notebook()
        else:
            return heatmap
            
    def test_tendency():
    t28 = xa.backtest.Tendency28(start="2018-01-01", verbose=True, initial_money=600000)
    t28.backtest()
    sys = t28.get_current_mul().summary()
    assert sys[sys["name"] == "total"].iloc[0]["Historical maximum occupancy"] == 600000


def test_balance():
    fundlist = ["002146", "001316", "001182"]
    portfolio_dict = {"F" + f: 1 / len(fundlist) for f in fundlist}
    check_dates = pd.date_range("2019-01-01", "2020-08-01", freq="Q")
    bt = xa.backtest.Balance(
        start=pd.Timestamp("2019-01-04"),
        totmoney=10000,
        check_dates=check_dates,
        portfolio_dict=portfolio_dict,
        verbose=True,
    )

    bt.backtest()
    sys = bt.get_current_mul()
    sys.summary("2020-08-15")
    assert round(sys.xirrrate("2020-08-14"), 2) == 0.18
    def next(self):
        if not self.position:
            if self.crossover > 0:
                amount_to_invest = 0.95 * self.broker.cash
                self.size = int(
                    amount_to_invest / self.data.close
                )
                print(
                    "Buy {} shares of {} at {}".format(
                        self.size, "600519", self.data.close[0]
                    )
                )
                self.buy(size=self.size)
        else:
            if self.crossover < 0:
                print(
                    "Sell {} shares of {} at {}".format(
                        self.size, "600519", self.data.close[0]
                    )
                )
                self.close()


if __name__ == "__main__":
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MyStrategy)
    symbol = "600519"
    df = ts.get_k_data(symbol, start="2018-01-01", end="2023-03-20")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date", drop=True)
    data = bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4,
        openinterest=-1,
    )
    cerebro.adddata(data)
    cerebro.broker.setcash(1000000.0)
    cerebro.broker.setcommission(commission=0.001)
    print("Starting Portfolio Value: %.2f" % cerebro.broker.getvalue())
    print("Final Portfolio Value: %.2f" % cerebro.broker.getvalue())
    cerebro.plot()
