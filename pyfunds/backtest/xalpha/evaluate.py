# -*- coding: utf-8 -*-
"""
modules for evaluation and comparison on multiple object with price dataframe
"""

from pyecharts.charts import HeatMap, Line

from xalpha.cons import convert_date, heatmap_opts, line_opts, yesterdayobj


class evaluate:
    """
   A comparison class for multiple info objects, as long as the object being compared implements the price property, which is pandas with date and netvalue columns. DataFrame.
Further, you can also use bcmkset's :class:'xalpha.multiple.mulfix' class as input, but you need to specify the name and code properties of the following object in advance.
Since this category requires that the net value tables of each fund can be strictly aligned, it is necessary to complete the different QDII funds on holidays and in China, and since the
first fund is the benchmark, the first input is not recommended to be a QDII fund

    :param fundobjs: info object，Or, as mentioned earlier, everything has a price table
    :param start: date string or object, The start time of the comparison, which defaults to the most recent start time in all price tables.
However, it should be noted that due to the pulled fund NAV table, the NAV data is often missing in the first few days, and even using the default time may not be able to align all the NAV data.
Therefore, it is recommended to manually set the start time to about a week after the nearest start time.
    """

    def __init__(self, *fundobjs, start=None):
        self.fundobjs = fundobjs
        self.totprice = (
            self.fundobjs[0]
            .price[["date", "netvalue"]]
            .rename(columns={"netvalue": fundobjs[0].code})
        )
        for fundobj in fundobjs[1:]:
            self.totprice = self.totprice.merge(
                fundobj.price[["date", "netvalue"]].rename(
                    columns={"netvalue": fundobj.code}
                ),
                on="date",
            )

        startdate = self.totprice.iloc[0].date
        if start is None:
            self.start = startdate
        else:
            start = convert_date(start)
            if start < startdate:
                raise Exception("Too early start date")
            else:
                self.start = start
                self.totprice = self.totprice[self.totprice["date"] >= self.start]
        self.totprice = self.totprice.reset_index(drop=True)
        for col in self.totprice.columns:
            if col != "date":
                self.totprice[col] = self.totprice[col] / self.totprice[col].iloc[0]

    def v_netvalue(self, end=yesterdayobj(), vopts=None, rendered=True):
        """
       If the starting point is aligned and normalized, the net value of each reference fund or index is compared and visualized

        :param end: string or object of date, the end date of the line
        :param vkwds: pyechart line.add() options
        :param vopts: dict, options for pyecharts instead of builtin settings
        :returns: pyecharts.charts.Line.render_notebook()
        """
        partprice = self.totprice[self.totprice["date"] <= end]

        line = Line()
        if vopts is None:
            vopts = line_opts
        line.set_global_opts(**vopts)
        line.add_xaxis([d.date() for d in list(partprice.date)])
        for fund in self.fundobjs:
            line.add_yaxis(
                series_name=fund.name,
                y_axis=list(partprice[fund.code]),
                is_symbol_show=False,
            )
        if rendered:
            return line.render_notebook()
        else:
            return line

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
        heatmap.add_yaxis(series_name="相关性", yaxis_data=x_axis, value=data)
        if vopts is None:
            vopts = heatmap_opts
        heatmap.set_global_opts(**vopts)
        if rendered:
            return heatmap.render_notebook()
        else:
            return heatmap
