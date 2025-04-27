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
