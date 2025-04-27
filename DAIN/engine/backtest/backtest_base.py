# coding:utf-8
import matplotlib.pyplot as plt
from pandas import DataFrame


class BacktestStrategyTemplate:
    name = "BacktestStrategyTemplate"

    def __init__(self, stock_code, bars: DataFrame, days=250):
        self.stock_code = stock_code
        self.days = days

        self.bars = bars
        self.signals = []

    def output_earning_rate(self):
        df = self.bars[-self.days :]
        df["signals"] = self.signals
        df["strategy"] = (1 + df.close.pct_change(1).fillna(0) * self.signals).cumprod()
        df["base"] = df["close"] / df["close"][0]
        print(df["strategy"].values[-1:])
        return df

    def show_plt(self):
        df = self.output_earning_rate()
        fig, axes = plt.subplots(2, 1, sharex=True, figsize=(18, 12))
        df[["strategy", "base", "signals"]].plot(
            ax=axes[0], grid=True, title="收益", figsize=(20, 10)
        )
        self.show_score(df, axes[1])
        plt.show()

    def show_score(self, df, ax):
        df["score"] = self.get_scores(df)
        df.score.plot(ax=ax, grid=True, title="score", figsize=(20, 10))

    def process(self):
        position = 0
        for i in range(self.days):

            singal = self.get_singal(self.bars[: -self.days + i - 1])
            if singal == -1:

                self.signals.append(position)
            else:
                position = singal
                self.signals.append(singal)

    def get_singal(self, bars: DataFrame):
        return 0

    def get_scores(self, df: DataFrame):
        return 0
