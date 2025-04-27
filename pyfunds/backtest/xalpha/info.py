# -*- coding: utf-8 -*-
"""
modules of info class, including cashinfo, indexinfo and fundinfo class
"""

import os
import csv
import datetime as dt
import json
import re
import logging
from functools import lru_cache

import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import exc

import xalpha.remain as rm
from xalpha.cons import (
    convert_date,
    droplist,
    myround,
    opendate,
    yesterday,
    yesterdaydash,
    yesterdayobj,
    today_obj,
    rget,
    rget_json,
    _float,
)
from xalpha.exceptions import FundTypeError, TradeBehaviorError, ParserFailure
from xalpha.indicator import indicator

_warnmess = "Something weird on redem fee, please adjust self.segment by hand"
logger = logging.getLogger(__name__)


def _shengoucal(sg, sgf, value, label):
    """
    Infer the share of buying fund by money input, the rate of fee in the unit of %,
        and netvalue of fund

    :param sg: positive float, 申购金额
    :param sgf: positive float, 申购费，以％为单位，如 0.15 表示 0.15%
    :param value: positive float, 对应产品的单位净值
    :param label: integer, 1 代表份额正常进行四舍五入， 2 代表份额直接舍去小数点两位之后。金额部分都是四舍五入
    :returns: tuple of two positive float, 净申购金额和申购份额
    """
    jsg = myround(sg / (1 + sgf * 1e-2))
    share = myround(jsg / value, label)
    return (jsg, share)


def _nfloat(string):
    """
    deal with comment column in fundinfo price table,
    positive value for fenhong and negative value for chaifen,
    keep other unrocognized pattern as original string

    :param string: string of input from original data
    :returns: make fenhong and songpei as float number
    """
    result = 0
    if string:
        try:
            result = float(string)
        except ValueError:
            if re.match(r'"Dividends\D*(\d*\.\d*)\D*"', string):
                result = float(re.match(r'"Dividends\D*(\d*\.\d*)\D*"', string).group(1))
            elif re.match(r".*cash(\d*\.\d*)\D*", string):
                result = float(re.match(r".*cash(\d*\.\d*)\D*", string).group(1))
            elif re.match(r".*Converted(\d*\.\d*)\D*", string):
                result = -float(re.match(r".*Converted(\d*\.\d*)\D*", string).group(1))
            elif re.match(r'"Split\D*(\d*\.\d*)\D*"', string):
                result = -float(re.match(r'"Split\D*(\d*\.\d*)\D*"', string).group(1))
            elif re.match(r"\D*Split(\d*\.\d*)\D*", string):
                result = -float(re.match(r"\D*Split(\d*\.\d*)\D*", string).group(1))
            else:
                logger.warning("The comment col cannot be converted: %s" % string)
                result = string
    return result


class FundReport:
    """
  Provides an interface to view various fund reports
    """

    def __init__(self, code):
        self.code = code
        r = rget(
            "http://api.fund.eastmoney.com/f10/JJGG?callback=&fundcode={code}&pageIndex=1&pageSize=20&type={type_}".format(
                code=code, type_="3"
            ),
            headers={
                "Referer": "http://fundf10.eastmoney.com/jjgg_{code}_3.html".format(
                    code=code
                )
            },
        )
        self.report_list = r.json()["Data"]
        self.report_detail = {}

    def get_report(self, no=0, id_=None):
        """

        :param no: int。
        :param id_: id
        :return:
        """
        if id_:
            report_url = "https://np-cnotice-fund.eastmoney.com/api/content/ann?client_source=web_fund&show_all=1&art_code={id_}".format(
                id_=id_
            )

        if not self.report_detail.get(no):
            report_url = "https://np-cnotice-fund.eastmoney.com/api/content/ann?client_source=web_fund&show_all=1&art_code={id_}".format(
                id_=self.report_list[no]["ID"]
            )

            # report_url = "http://fund.eastmoney.com/gonggao/{code},{id_}.html".format(
            #     code=self.code, id_=self.report_list[no]["ID"]
            # )
            # r = rget(report_url)
            # b = BeautifulSoup(r.text, "lxml")
            # seasonr = b.find("pre")
            # sr = [s.string.strip() for s in seasonr.findAll("p") if s.string]
        r = rget_json(report_url)

        sr = r["data"]["notice_content"]
        sr = [s.strip() for s in sr.split("\n") if s.strip()]
        self.report_detail[no] = sr

        return sr

    def show_report_list(self, type_=3):
        """

        :param type_: int。Column 0, column 1, the meaning of each column, please refer to the Tian Tian Fund Fund Report page.
        :return:
        """
        r = rget(
            "http://api.fund.eastmoney.com/f10/JJGG?callback=&fundcode={code}&pageIndex=1&pageSize=20&type={type_}".format(
                code=self.code, type_=str(type_)
            ),
            headers={
                "Referer": "http://fundf10.eastmoney.com/jjgg_{code}_3.html".format(
                    code=self.code
                )
            },
        )
        return r.json()["Data"]

    def analyse_report(self, no=0):
        l = self.get_report(no)
        d = {}
        d["title"] = ""
        for s in l[:5]:
            if s.startswith("manage"):
                break
            d["title"] += s + " "
        for i, s in enumerate(l):
            if s.startswith("Performance benchmarks"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    if l[i + 1][0] != "B":
                        d["benchmark"] = ss[-1] + l[i + 1]
                    else:
                        d["benchmark"] = ss[-1]
            elif s.startswith("Fund Managers"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["company"] = ss[-1]
            elif s.startswith("Fund custodian"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["bank"] = ss[-1]
            elif s.startswith("Abbreviation in the field"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["shortname"] = ss[-1]
            elif s.startswith("Fund master code"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["code"] = ss[-1]
            elif s.startswith("The total number of fund shares at the end of the reporting period"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["share"] = ss[-1]
            elif s.startswith("The effective date of the fund contract"):
                ss = [s for s in s.split("  ") if s.strip()]
                if len(ss) == 2:
                    d["start_date"] = ss[-1]
        return d


@lru_cache()
def get_fund_holdings(code, year="", season="", month="", category="jjcc"):
    """
   Get detailed information about the fund's underlying holdings

    :param code: str. 6 The fund code
    :param year:  int. eg. 2019
    :param season: int, 1,2,3,4
    :param month: Optional[int].
    :param category: str. stock
    :return: pd.DataFrame or None.
    """
    if not month and season:
        month = 3 * int(season)
    if category in ["stock", "stocks", "jjcc", "", "gp", "s"]:
        category = "jjcc"
    elif category in ["bond", "bonds", "zq", "zqcc", "b"]:
        category = "zqcc"
    else:
        raise ParserFailure("unrecognized category %s" % category)
    if code.startswith("F"):
        code = code[1:]
    r = rget(
        "http://fundf10.eastmoney.com/FundArchivesDatas.aspx?type={category}&code={code}&topline=10&\
year={year}&month={month}".format(
            year=str(year), month=str(month), code=code, category=category
        ),
        headers={
            "Host": "fundf10.eastmoney.com",
            "Referer": "http://fundf10.eastmoney.com/ccmx_{code}.html".format(
                code=code
            ),
        },
    )
    if len(r.text) < 50:
        return
        # raise ParserFailure(
        #     "This fund has no holdings on stock or bonds in this period"
        # )
    s = BeautifulSoup(
        re.match("[\s\S]*apidata={ content:(.*),arryear:", r.text).groups()[0], "lxml"
    )
    if len(s.text) < 30:
        return
        # raise ParserFailure(
        #     "This fund has no holdings on stock or bonds in this period"
        # )
    timeline = [
        i.string for i in s.findAll("font", class_="px12") if i.text.startswith("2")
    ]
    ind = 0
    if month:
        for i, d in enumerate(timeline):
            if d.split("-")[1][-1] == str(month)[-1]:  # avoid 09 compare to 9
                ind = i
                break
        else:
            return  # not update to this month
    t1 = s.findAll("table")[ind]
    main = [[j.text for j in i.contents] for i in t1.findAll("tr")[1:]]
    cols = [j.text for j in t1.findAll("tr")[0].contents if j.text.strip()]
    icode = 1
    iname = 2
    iratio = 4
    ishare = 5
    ivalue = 6
    for j, col in enumerate(cols):
        if col.endswith("code"):
            icode = j
        elif col.endswith("name"):
            iname = j
        elif col.endswith("proportion"):
            iratio = j
        elif col.startswith("Number of shares"):
            ishare = j
        elif col.startswith("Market value of the position"):
            ivalue = j
    if category == "jjcc":
        result = {"code": [], "name": [], "ratio": [], "share": [], "value": []}
        for l in main:
            result["code"].append(l[icode])
            result["name"].append(l[iname])
            result["ratio"].append(float(l[iratio][:-1]))
            result["share"].append(_float(l[ishare]))
            result["value"].append(_float(l[ivalue]))
    elif category == "zqcc":
        result = {"code": [], "name": [], "ratio": [], "value": []}
        for l in main:
            result["code"].append(l[1])
            result["name"].append(l[2])
            result["ratio"].append(float(l[3][:-1]))
            result["value"].append(_float(l[4]))
    return pd.DataFrame(result)


class basicinfo(indicator):
    """
    Base class for info of fund, index or even cash,
    which cannot be directly instantiate, the basic implementation consider
    redemption fee as zero when shuhui() function is implemented

    :param code: string of code for specific product
    :param fetch: boolean, when open the fetch option, the class will try fetching from local files first in the init
    :param save: boolean, when open the save option, automatically save the class to files
    :param path: string, the file path prefix of IO. Or in sql case, path is the engine from sqlalchemy.
    :param form: string, the format of IO, options including: 'csv','sql'
    :param round_label: int, default 0 or 1, label to the different round scheme of shares, reserved for fundinfo class.
    :param dividend_label: int, default 0 or 1. 0
    :param value_label: int, default 0 or 1. 1
    """

    def __init__(
        self,
        code,
        fetch=False,
        save=False,
        path="",
        form="csv",
        round_label=0,
        dividend_label=0,
        value_label=0,
    ):
        # The logic for incremental IO is handled by the basicinfo class, and for specific subclasses, only _save_form and _fetch_form and the update function are implemented
        self.code = code

        self.round_label = round_label
        self.dividend_label = dividend_label
        self.value_label = value_label
        self.specialdate = []
        self.fenhongdate = []
        self.zhesuandate = []

        # compatible with new ``xa.set_backend()`` API
        import xalpha.universal as xu

        if (xu.ioconf["backend"] in ["csv", "sql"]) and (not path):
            fetch = True
            save = True
            form = xu.ioconf["backend"]
            path = xu.ioconf["path"]
            if xu.ioconf["backend"] == "csv":
                path = os.path.join(path, xu.ioconf["prefix"] + "INFO-")
        self.format = form
        if fetch is False:
            self._basic_init()  # update self. name rate and price table
        else:
            try:
                self.fetch(path, self.format)
                df = self.update()  # update the price table as well as the file
                if (df is not None) and save is True:
                    self.save(path, self.format, option="a", delta=df)

            except (FileNotFoundError, exc.ProgrammingError, exc.OperationalError) as e:
                logger.info("no saved copy of %s" % self.code)
                fetch = False
                self._basic_init()

        if (save is True) and (fetch is False):
            self.save(path, self.format)

    def _basic_init(self):
        """
        set self. name rate and price (dataframe) as well as other necessary attr of info()
        """
        # below lines are just showcase, this function must be rewrite by child classes
        # self.name = 'unknown'
        # self.rate = 0
        # self.price = pd.DataFrame(data={'date':[],'netvalue':[],'comment':[]})
        raise NotImplementedError

    def shengou(self, value, date, fee=None):
        """
        give the realdate deltacash deltashare tuple based on purchase date and purchase amount
        if the date is not a trade date, then the purchase would happen on the next trade day, if the date is
        in the furture, then the trade date is taken as yesterday.

        :param value: the money for purchase
        :param date: string or object of date
        :param fee: the rate for shengou, default None and info.rate will be used, ok for most cases
        :returns: three elements tuple, the first is the actual dateobj of commit
            the second is a negative float for cashin,
            the third is a positive float for share increase
        """
        if fee is None:
            fee = self.rate
        row = self.price[self.price["date"] >= date].iloc[0]
        share = _shengoucal(value, fee, row.netvalue, label=self.round_label + 1)[1]
        return (row.date, -myround(value), share)

    def shuhui(self, share, date, rem, value_label=None, fee=None):
        """
        give the cashout considering redemption rates as zero.
        if the date is not a trade date, then the purchase would happen on the next trade day, if the date is
        in the furture, then the trade date is taken as yesterday.

        :param share: float or int, number of shares to be sold. if value_label=1, its cash to be sold.
        :param date: string or object of date
        :param rem: positions with time list
        :param value_label: default None, value_label will be chosen by info.value_label, determining
                whether shuhui by share 0 or value 1. value_label = 0 will rewrite self.value_label = 1
        :param fee: default None, determined automatically, suggested for most of the cases.
                Otherwise 0.015 means 1.5% in shuhui, this is different than fee in shengou, where 1.5 is for 1.5% fee
        :returns: three elements tuple, the first is dateobj
            the second is a positive float for cashout,
            the third is a negative float for share decrease
        """
        if self.value_label == 0 or value_label == 0:
            return self._shuhui_by_share(share, date, rem)
        elif self.value_label == 1:  # Redemption by amount, only money market funds with no redemption fee are supported
            partprice = self.price[self.price["date"] >= date]
            if len(partprice) == 0:
                row = self.price[self.price["date"] < date].iloc[-1]
            else:
                row = partprice.iloc[0]
            share = share / row.netvalue
            return self._shuhui_by_share(share, date, rem, fee=fee)

    def _shuhui_by_share(self, share, date, rem, fee=None):
        date = convert_date(date)
        tots = sum([remitem[1] for remitem in rem if remitem[0] <= date])
        if share > tots:
            sh = tots
        else:
            sh = share
        partprice = self.price[self.price["date"] >= date]
        if len(partprice) == 0:
            row = self.price[self.price["date"] < date].iloc[-1]
        else:
            row = partprice.iloc[0]
        value = myround(sh * row.netvalue)
        if fee is not None:
            value = (1 - fee) * value
        return (
            row.date,
            value,
            -myround(sh),
        )  # TODO: Whether myround is also related to round_label here remains to be examined

    def info(self):
        """
        print basic info on the class
        """
        print("fund name: %s" % self.name)
        print("fund code: %s" % self.code)
        print("fund purchase fee: %s%%" % self.rate)

    def __repr__(self):
        return self.name

    def save(self, path, form=None, option="r", delta=None):
        """
        save info to files, this function is designed to redirect to more specific functions

        :param path: string of the folder path prefix! or engine obj from sqlalchemy
        :param form: string, option:'csv'
        :param option: string, r for replace and a for append output
        :param delta: if option is a, you have to specify the delta which is the incremental part of price table
        """
        if form is None:
            form = self.format
        if form == "csv" and option == "r":
            self._save_csv(path)
        elif form == "csv" and option == "a":
            self._save_csv_a(path, delta)
        elif form == "sql" and option == "r":
            self._save_sql(path)
        elif form == "sql" and option == "a":
            self._save_sql_a(path, delta)

    def _save_csv_a(self, path, df):
        df.sort_index(axis=1).to_csv(
            path + self.code + ".csv",
            mode="a",
            header=None,
            index=False,
            date_format="%Y-%m-%d",
        )

    def _save_sql_a(self, path, df):
        df.sort_index(axis=1).to_sql(
            "xa" + self.code, path, if_exists="append", index=False
        )

    def fetch(self, path, form=None):
        """
        fetch info from files

        :param path: string of the folder path prefix! end with / in csv case;
            engine from sqlalchemy.create_engine() in sql case.
        :param form: string, option:'csv' or 'sql
        """
        if form is None:
            form = self.format
        if form == "csv":
            self._fetch_csv(path)
        elif form == "sql":
            self._fetch_sql(path)

    def update(self):
        """
        Incremental updates to the class's price list and incremental storage are appropriate for fetch open scenarios

        :returns: the incremental part of price table or None if no incremental part exsits
        """
        raise NotImplementedError


class fundinfo(basicinfo):
    """
    class for specific fund with basic info and every day values

    :param code: str,
    :param round_label: integer 0 or 1, 取
        label
    :param dividend_label: int, default 0 or 1. 0
    :param fetch: boolean, when open the fetch option, the class will try fetching from local files first in the init
    :param save: boolean, when open the save option, automatically save the class to files
    :param path: string, the file path prefix of IO
    :param form: string, the format of IO, options including: 'csv'
    """

    def __init__(
        self,
        code,
        round_label=0,
        dividend_label=0,
        fetch=False,
        save=False,
        path="",
        form="csv",
        priceonly=False,
    ):
        if round_label == 1 or (code in droplist):
            label = 1  # the scheme of round down on share purchase
        else:
            label = 0
        if code.startswith("F") and code[1:].isdigit():
            code = code[1:]
        elif code.startswith("M") and code[1:].isdigit():
            raise FundTypeError(
                "This code seems to be a mfund, use ``mfundinfo`` instead"
            )
        code = code.zfill(6)  # 1234 is the same as 001234
        self._url = (
            "http://fund.eastmoney.com/pingzhongdata/" + code + ".js"
        )  # js url api for info of certain fund
        self._feeurl = (
            "http://fund.eastmoney.com/f10/jjfl_" + code + ".html"
        )  # html url for trade fees info of certain fund
        self.priceonly = priceonly

        super().__init__(
            code,
            fetch=fetch,
            save=save,
            path=path,
            form=form,
            round_label=label,
            dividend_label=dividend_label,
        )

        self.special = self.price[self.price["comment"] != 0]
        self.specialdate = list(self.special["date"])
        # date with nonvanishing comment, usually fenhong or zhesuan
        try:
            self.fenhongdate = list(self.price[self.price["comment"] > 0]["date"])
            self.zhesuandate = list(self.price[self.price["comment"] < 0]["date"])
        except TypeError:
            print("There are still string comments for the fund!")

    def _basic_init(self):
        if self.code.startswith("96"):
            self._hkfund_init()
            return
        self._page = rget(self._url)
        if self._page.status_code == 404:
            raise ParserFailure("Unrecognized fund, please check fund code you input.")
        if self._page.text[:800].find("Data_millionCopiesIncome") >= 0:
            raise FundTypeError("This code seems to be a mfund, use mfundinfo instead")

        l = re.match(
            r"[\s\S]*Data_netWorthTrend = ([^;]*);[\s\S]*", self._page.text
        ).groups()[0]
        l = l.replace("null", "None")
        l = eval(l)
        ltot = re.match(
            r"[\s\S]*Data_ACWorthTrend = ([^;]*);[\s\S]*", self._page.text
        ).groups()[
            0
        ]  # .* doesn't match \n
        ltot = ltot.replace("null", "None")
        ltot = eval(ltot)
        ## timestamp transform tzinfo must be taken into consideration
        tz_bj = dt.timezone(dt.timedelta(hours=8))
        infodict = {
            "date": [
                dt.datetime.fromtimestamp(int(d["x"]) / 1e3, tz=tz_bj).replace(
                    tzinfo=None
                )
                for d in l
            ],
            "netvalue": [float(d["y"]) for d in l],
            "comment": [_nfloat(d["unitMoney"]) for d in l],
        }

        if len(l) == len(ltot):
            infodict["totvalue"] = [d[1] for d in ltot]

        try:
            rate = float(
                eval(
                    re.match(
                        r"[\s\S]*fund_Rate=([^;]*);[\s\S]*", self._page.text
                    ).groups()[0]
                )
            )
        except ValueError:
            rate = 0
            logger.info("warning: this fund has no data for rate")  # know cases: ETF

        name = eval(
            re.match(r"[\s\S]*fS_name = ([^;]*);[\s\S]*", self._page.text).groups()[0]
        )

        self.rate = rate
        # shengou rate in tiantianjijin, daeshengou rate discount is not considered
        self.name = name  # the name of the fund
        df = pd.DataFrame(data=infodict)
        df = df[df["date"].isin(opendate)]
        df = df.reset_index(drop=True)
        if len(df) == 0:
            raise ParserFailure("no price table found for this fund %s" % self.code)
        self.price = df[df["date"] <= yesterdaydash()]
        # deal with the redemption fee attrs finally
        if not self.priceonly:
            self._feepreprocess()

    def _feepreprocess(self):
        """
        Preprocess to add self.feeinfo and self.segment attr according to redemption fee info
        """
        feepage = rget(self._feeurl)
        soup = BeautifulSoup(
            feepage.text, "lxml"
        )  # parse the redemption fee html page with beautiful soup
        somethingwrong = False
        if not soup.findAll("a", {"name": "shfl"}):
            somethingwrong = True
            logger.warning("%sThe fund redemption information is blank, which may be due to the fact that the fund has ceased operation" % self.code)
            self.feeinfo = []
        else:
            self.feeinfo = [
                item.string
                for item in soup.findAll("a", {"name": "shfl"})[
                    0
                ].parent.parent.next_sibling.next_sibling.find_all("td")
                if item.string != "---"
            ]
        # this could be [], known case 510030

        if not self.feeinfo or len(self.feeinfo) % 2 != 0:
            somethingwrong = True
        else:
            for item in self.feeinfo:
                if "开放期" in item or "封闭" in item or "开放日期" in item or "运作期" in item:
                    # At the moment, there is no plan to perfectly maintain the redemption fee treatment of fixed opening funds
                    somethingwrong = True
        if somethingwrong:
            logger.warning(
                "%s The redemption fee information is abnormal, mostly because of fixed opening funds, closed-end funds or on-market ETF: %s" % (self.code, self.feeinfo)
            )
            self.feeinfo = ["Less than 7 days", "1.50%", "Greater than or equal to 7 days", "0.00%"]
        # print(self.feeinfo)
        try:
            self.segment = fundinfo._piecewise(self.feeinfo)
        except (ValueError, IndexError) as e:
            logger.warning(
                "%s If the redemption fee information is abnormal, please set it manually ``self.segment`` 和 ``self.feeinfo``: %s"
                % (self.code, self.feeinfo)
            )
            # below is default one
            self.feeinfo = ["Less than 7 days", "1.50%", "Greater than or equal to 7 days", "0.00%"]
            self.segment = fundinfo._piecewise(self.feeinfo)

    @staticmethod
    def _piecewise(a):
        """
        Transform the words list into a pure number segment list for redemption fee, eg. [[0,7],[7,365],[365]]
        """

        b = [
            (
                a[2 * i]
                .replace("Holding period", "")
                .replace("Held during the open operation period", "")
                .replace("Duration of share holding", "")
            ).split("，")
            for i in range(int(len(a) / 2))
        ]

        for j, tem in enumerate(b):
            for i, num in enumerate(tem):
                if num[-1] == "天":
                    num = int(num[:-1])
                elif num[-1] == "月":
                    num = int(num[:-1]) * 30
                elif num == ".5年":
                    num = 183
                else:
                    num = int(float(num[:-1]) * 365)
                b[j][i] = num
        if len(b[0]) == 1:
            b[0].insert(0, 0)
        elif len(b[0]) == 2:
            b[0][0] = 0
        else:
            print(_warnmess)
        for i in range(len(b) - 1):
            if b[i][1] - b[i + 1][0] == -1:
                b[i][1] = b[i + 1][0]
            elif b[i][1] == b[i + 1][0]:
                pass
            else:
                print(_warnmess)

        return b

    def feedecision(self, day):
        """
        give the redemption rate in percent unit based on the days difference between purchase and redemption

        :param day: integer，
        :returns: float，
        """
        i = -1
        for seg in self.segment:
            i += 2
            if day - seg[0] >= 0 and (len(seg) == 1 or day - seg[-1] < 0):
                return float(self.feeinfo[i].strip("%"))
        return 0  # error backup, in case there is sth wrong in segment

    def set_feeinfo(self, feeinfo):
        """
      Set the correct redemption rate information

        :param feeinfo: List[string]
        """
        self.feeinfo = feeinfo
        self.segment = self._piecewise(feeinfo)

    def set_price(self, col, date, value):
        """
       Set and correct the comment or price information of a single day in the price table

        :param col: str. "comment", "netvalue" or "totvalue"
        :param date: “%Y%m%d”
        :param value:
        """
        self.price.loc[self.price["date"] == date, col] = value
        ## update special in case new comment is added
        self.special = self.price[self.price["comment"] != 0]
        self.specialdate = list(self.special["date"])

    def shuhui(self, share, date, rem, value_label=None, fee=None):
        """
        give the cashout based on rem term considering redemption rates

        :returns: three elements tuple, the first is dateobj
            the second is a positive float for cashout,
            the third is a negative float for share decrease
        """
        # 		 value = myround(share*self.price[self.price['date']==date].iloc[0].netvalue)
        date = convert_date(date)
        partprice = self.price[self.price["date"] >= date]
        if len(partprice) == 0:
            row = self.price[self.price["date"] < date].iloc[-1]
        else:
            row = partprice.iloc[0]
        soldrem, _ = rm.sell(rem, share, row.date)
        value = 0
        sh = myround(sum([item[1] for item in soldrem]))
        for d, s in soldrem:
            if fee is None:
                tmpfee = self.feedecision((row.date - d).days) * 1e-2
            else:
                tmpfee = fee
            value += myround(
                s * row.netvalue * (1 - tmpfee)
            )  # TODO: round_label whether play a role here?
        return (row.date, value, -sh)

    def info(self):
        super().info()
        print("fund redemption fee info: %s" % self.feeinfo)

    def _save_csv(self, path):
        """
        save the information and pricetable into path+code.csv, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  string of folder path
        """
        s = json.dumps(
            {
                "feeinfo": self.feeinfo,
                "name": self.name,
                "rate": self.rate,
                "segment": self.segment,
            }
        )
        df = pd.DataFrame(
            [[s, 0, 0, 0]], columns=["date", "netvalue", "comment", "totvalue"]
        )
        df = df.append(self.price, ignore_index=True, sort=True)
        df.sort_index(axis=1).to_csv(
            path + self.code + ".csv", index=False, date_format="%Y-%m-%d"
        )

    def _fetch_csv(self, path):
        """
        fetch the information and pricetable from path+code.csv, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  string of folder path
        """
        try:
            content = pd.read_csv(path + self.code + ".csv")
            pricetable = content.iloc[1:]
            datel = list(pd.to_datetime(pricetable.date))
            self.price = pricetable[["netvalue", "totvalue", "comment"]]
            self.price["date"] = datel
            saveinfo = json.loads(content.iloc[0].date)
            if not isinstance(saveinfo, dict):
                raise FundTypeError("This csv doesn't looks like from fundinfo")
            self.segment = saveinfo["segment"]
            self.feeinfo = saveinfo["feeinfo"]
            self.name = saveinfo["name"]
            self.rate = saveinfo["rate"]
        except FileNotFoundError as e:
            # print('no saved copy of fund %s' % self.code)
            raise e

    def _save_sql(self, path):
        """
        save the information and pricetable into sql, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        s = json.dumps(
            {
                "feeinfo": self.feeinfo,
                "name": self.name,
                "rate": self.rate,
                "segment": self.segment,
            }
        )
        df = pd.DataFrame(
            [[pd.Timestamp("1990-01-01"), 0, s, 0]],
            columns=["date", "netvalue", "comment", "totvalue"],
        )
        df = df.append(self.price, ignore_index=True, sort=True)
        df.sort_index(axis=1).to_sql(
            "xa" + self.code, con=path, if_exists="replace", index=False
        )

    def _fetch_sql(self, path):
        """
        fetch the information and pricetable from sql, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        try:
            content = pd.read_sql("xa" + self.code, path)
            pricetable = content.iloc[1:]
            commentl = [float(com) for com in pricetable.comment]
            self.price = pricetable[["date", "netvalue", "totvalue"]]
            self.price["comment"] = commentl
            saveinfo = json.loads(content.iloc[0].comment)
            if not isinstance(saveinfo, dict):
                raise FundTypeError("This csv doesn't looks like from fundinfo")
            self.segment = saveinfo["segment"]
            self.feeinfo = saveinfo["feeinfo"]
            self.name = saveinfo["name"]
            self.rate = saveinfo["rate"]
        except exc.ProgrammingError as e:
            # print('no saved copy of %s' % self.code)
            raise e

    def _hk_update(self):
        # For the time being, I am not sure that there is no bug in the incremental update logic, and it will take time to verify
        # Pay attention to the synchronous update of dividends when the incremental update is made
        lastdate = self.price.iloc[-1].date
        diffdays = (yesterdayobj() - lastdate).days
        if diffdays == 0:
            return None
        import xalpha.universal as xu

        df = xu.get_daily("F" + self.code, start=lastdate.strftime("%Y%m%d"))
        df = df[df["date"].isin(opendate)]
        df = df.reset_index(drop=True)
        df = df[df["date"] <= yesterdayobj()]
        df = df[df["date"] > lastdate]

        if len(df) != 0:
            r = self._hk_bonus(start=lastdate.strftime("%Y-%m-%d"))
            df["comment"] = [0 for _ in range(len(df))]
            df["netvalue"] = df["close"]
            df = df.drop("close", axis=1)
            df = df[df["date"].isin(opendate)]
            for d in r:
                df.loc[df["date"] == d["EXDDATE"], "comment"] = d["BONUS"]
            self.price = self.price.append(df, ignore_index=True, sort=True)
            return df

    def update(self):
        """
        function to incrementally update the pricetable after fetch the old one
        """
        if self.code.startswith("96"):
            return self._hk_update()
        lastdate = self.price.iloc[-1].date
        diffdays = (yesterdayobj() - lastdate).days
        if (
            diffdays == 0
        ):  ## for some QDII, this value is 1, anyways, trying update is compatible (d+2 update)
            return None
        self._updateurl = (
            "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
            + self.code
            + "&page=1&per=1"
        )
        con = rget(self._updateurl)
        soup = BeautifulSoup(con.text, "lxml")
        items = soup.findAll("td")
        if dt.datetime.strptime(str(items[0].string), "%Y-%m-%d") == today_obj():
            diffdays += 1
        if diffdays <= 10:
            self._updateurl = (
                "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
                + self.code
                + "&page=1&per="
                + str(diffdays)
            )
            con = rget(self._updateurl)
            soup = BeautifulSoup(con.text, "lxml")
            items = soup.findAll("td")
        elif (
            diffdays > 10
        ):  ## there is a 20 item per page limit in the API, so to be safe, we query each page by 10 items only
            items = []
            for pg in range(1, int(diffdays / 10) + 2):
                self._updateurl = (
                    "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
                    + self.code
                    + "&page="
                    + str(pg)
                    + "&per=10"
                )
                con = rget(self._updateurl)
                soup = BeautifulSoup(con.text, "lxml")
                items.extend(soup.findAll("td"))
        else:
            raise TradeBehaviorError(
                "Weird incremental update: the saved copy has future records"
            )

        date = []
        netvalue = []
        totvalue = []
        comment = []
        for i in range(int(len(items) / 7)):
            ts = pd.Timestamp(str(items[7 * i].string))
            if (ts - lastdate).days > 0:
                date.append(ts)
                netvalue.append(_float(items[7 * i + 1].string))
                totvalue.append(_float(items[7 * i + 2].string))
                comment.append(_nfloat(items[7 * i + 6].string))
            else:
                break
        df = pd.DataFrame(
            {
                "date": date,
                "netvalue": netvalue,
                "totvalue": totvalue,
                "comment": comment,
            }
        )
        df = df.iloc[::-1]  ## reverse the time order
        df = df[df["date"].isin(opendate)]
        df = df.reset_index(drop=True)
        df = df[df["date"] <= yesterdayobj()]
        if len(df) != 0:
            self.price = self.price.append(df, ignore_index=True, sort=True)
            return df

    def get_holdings(self, year="", season="", month="", category="stock"):
        return get_fund_holdings(
            self.code, year, season=season, month=month, category=category
        )

    def get_stock_holdings(self, year="", season="", month=""):
        """
        持仓个股细节

        :param year:
        :param season:
        :param month:
        :return: pd.DataFrame
        """
        return get_fund_holdings(
            self.code, year, season=season, month=month, category="stock"
        )

    def get_bond_holdings(self, year="", season="", month=""):
        """
        持仓债券细节

        :param year:
        :param season:
        :param month:
        :return: pd.DataFrame
        """
        return get_fund_holdings(
            self.code, year, season=season, month=month, category="bond"
        )

    def get_portfolio_holdings(self, date=None):
        """
        持仓股债现金占比

        :param date:
        :return: Dict
        """
        if date is None:
            date = dt.datetime.now().strftime("%Y-%m-%d")
        import xalpha.universal as xu

        df = xu.get_daily("pt-F" + self.code, end=date)
        if df is not None:
            d = dict(df.iloc[-1])
            del d["assets"], d["date"]
            return d
        else:
            logger.warning("no portfolio information before %s" % date)
            return

    def get_industry_holdings(self, year="", season="", month="", threhold=0.5):
        """
        持仓行业占比

        :param year:
        :param season:
        :param month:
        :param threhold: float,Individual stock industries with positions less than this percentage will no longer be counted, and the speed will be accelerated
        :return:  Dict
        """


        from xalpha.universal import ttjjcode, get_industry_fromxq

        df = self.get_stock_holdings(year=year, season=season, month=month)
        if df is None:
            logger.warning(
                "%s has no stock holdings in %s y %s s. (Possible reason: 链接基金，债券基金)"
                % (self.code, year, season)
            )
            return
        d = {}
        for i, row in df.iterrows():
            if row["ratio"] < threhold:
                continue
            code = ttjjcode(row["code"])
            industry = get_industry_fromxq(code)["industryname"]
            if not industry.strip():
                logger.warning(
                    "%s has no industry information, cannot be classfied" % code
                )
            else:
                if industry not in d:
                    d[industry] = 0
                d[industry] += row["ratio"]
        return d

    def which_industry(self, threhold=1.0):
        """
        Experimental API
       When a single industry accounts for more than the threhold times of other industries, it is automatically determined as the corresponding industry fund
Note that the industry here may be more subdivided, resulting in the possibility that multiple industries are actually the same large industry and thus misjudged as a broad-based fund

        :param threhold: float
        :return: str
        """
        d = self.get_industry_holdings()
        l = sorted([(k, v) for k, v in d.items()], key=lambda s: -s[1])
        s0 = 0
        if l and l[0] and l[0][1]:
            s0 = l[0][1]
        s1 = sum([l[i][1] for i in range(1, len(l))])
        if s0 > threhold * s1:
            return "行业基金： " + l[0][0]
        else:
            return "宽基基金"

    def _hkfund_init(self):
        import xalpha.universal as xu

        # Mutual recognition funds also have net value on domestic market holidays, which are temporarily filtered, and it is uncertain whether it will cause compatibility problems
        self.meta = xu.get_rt("F" + self.code)
        self.start = self.meta["startdate"]
        self.name = self.meta["name"]
        self.price = xu.get_daily("F" + self.code, start=self.start)
        self.feeinfo = ["Less than 7 days", "0.00%", "Greater than or equal to 7 days", "0.00%"]  # c
        self.segment = fundinfo._piecewise(self.feeinfo)
        r = rget("http://overseas.1234567.com.cn/f10/FundSaleInfo/968012#SaleInfo")
        b = BeautifulSoup(r.text, "lxml")
        self.rate = _float(
            [
                c.strip()
                for c in b.select(".HK_Fund_Table.BigText")[5].text.split("\n")
                if c.strip()
            ][-1]
            .split("|")[-1]
            .strip()[:-1]
        )
        r = self._hk_bonus()
        df = self.price
        df["comment"] = [0 for _ in range(len(df))]
        df["netvalue"] = df["close"]
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"].isin(opendate)]
        for d in r:
            df.loc[df["date"] == d["EXDDATE"], "comment"] = d["BONUS"]
        df = df.drop("close", axis=1)
        self.price = df

    def _hk_bonus(self, start=None):
        """
        [summary]

        :param start: "%Y-%m-%d", defaults to None
        :type start: [type], optional
        """
        import xalpha.universal as xu

        todaydash = today_obj().strftime("%Y-%m-%d")
        if not start:
            start = self.price.iloc[0]["date"].strftime("%Y-%m-%d")
        pagesize = int(
            (today_obj() - dt.datetime.strptime(start, "%Y-%m-%d")).days / 5
        )
        self.hkfcode = xu.get_hkfcode(self.code)
        r = rget_json(
            "http://overseas.1234567.com.cn/overseasapi/OpenApiHander.ashx?\
api=HKFDApi&m=MethodJZ&hkfcode={hkfcode}&action=3&pageindex=0&pagesize={pagesize}&date1={startdash}&date2={enddash}&callback=".format(
                hkfcode=self.hkfcode,
                pagesize=pagesize,
                startdash=start,
                enddash=todaydash,
            )
        )
        return r["Data"]


class indexinfo(basicinfo):
    """
    Get everyday close price of specific index.
    In self.price table, totvalue column is the real index
    while netvalue comlumn is normalized to 1 for the start date.
    In principle, this class can also be used to save stock prices but the price is without adjusted.

    :param code: string with seven digitals! note the code here has an extra digit at the beginning,
        0 for sh and 1 for sz.
    :param value_label: int, default 0 or 1. If set to 1, 记账单数字按金额赎回。
    :param fetch: boolean, when open the fetch option, the class will try fetching from local files first in the init
    :param save: boolean, when open the save option, automatically save the class to files
    :param path: string, the file path prefix of IO
    :param form: string, the format of IO, options including: 'csv'
    """

    def __init__(
        self, code, value_label=0, fetch=False, save=False, path="", form="csv"
    ):
        date = yesterday()
        if code.startswith("SH") and code[2:].isdigit():
            code = "0" + code[2:]
        elif code.startswith("SZ") and code[2:].isdigit():
            code = "1" + code[2:]
        self.rate = 0
        self._url = (
            "http://quotes.money.163.com/service/chddata.html?code="
            + code
            + "&start=19901219&end="
            + date
            + "&fields=TCLOSE"
        )
        super().__init__(
            code, value_label=value_label, fetch=fetch, save=save, path=path, form=form
        )

    def _basic_init(self):
        raw = rget(self._url)
        raw.encoding = "gbk"
        cr = csv.reader(raw.text.splitlines(), delimiter=",")
        my_list = list(cr)
        factor = float(my_list[-1][3])
        dd = {
            "date": [
                dt.datetime.strptime(my_list[i + 1][0], "%Y-%m-%d")
                for i in range(len(my_list) - 1)
            ],
            "netvalue": [
                float(my_list[i + 1][3]) / factor for i in range(len(my_list) - 1)
            ],
            "totvalue": [float(my_list[i + 1][3]) for i in range(len(my_list) - 1)],
            "comment": [0 for _ in range(len(my_list) - 1)],
        }
        index = pd.DataFrame(data=dd)
        index = index.iloc[::-1]
        index = index.reset_index(drop=True)
        self.price = index[index["date"].isin(opendate)]
        self.price = self.price[self.price["date"] <= yesterdaydash()]
        self.name = my_list[-1][2]

    def _save_csv(self, path):
        """
        save the information and pricetable into path+code.csv, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  string of folder path
        """
        self.price.sort_index(axis=1).to_csv(
            path + self.code + ".csv", index=False, date_format="%Y-%m-%d"
        )

    def _fetch_csv(self, path):
        """
        fetch the information and pricetable from path+code.csv, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  string of folder path
        """
        try:
            pricetable = pd.read_csv(path + self.code + ".csv")
            datel = list(pd.to_datetime(pricetable.date))
            self.price = pricetable[["netvalue", "totvalue", "comment"]]
            self.price["date"] = datel

        except FileNotFoundError as e:
            # print('no saved copy of %s' % self.code)
            raise e

    def _save_sql(self, path):
        """
        save the information and pricetable into sql, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        self.price.sort_index(axis=1).to_sql(
            "xa" + self.code, con=path, if_exists="replace", index=False
        )

    def _fetch_sql(self, path):
        """
        fetch the information and pricetable from sql, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        try:
            pricetable = pd.read_sql("xa" + self.code, path)
            self.price = pricetable

        except exc.ProgrammingError as e:
            # print('no saved copy of %s' % self.code)
            raise e

    def update(self):
        lastdate = self.price.iloc[-1].date
        lastdatestr = lastdate.strftime("%Y%m%d")
        weight = self.price.iloc[1].totvalue
        self._updateurl = (
            "http://quotes.money.163.com/service/chddata.html?code="
            + self.code
            + "&start="
            + lastdatestr
            + "&end="
            + yesterday()
            + "&fields=TCLOSE"
        )
        df = pd.read_csv(self._updateurl, encoding="gb2312")
        self.name = df.iloc[0].loc["名称"]


class cashinfo(basicinfo):
    """
    A virtual class for remaining cash manage: behave like monetary fund

    :param interest: float, daily rate in the unit of 100%, note this is not a year return rate!
    :param start: str of date or dateobj, the virtual starting date of the cash fund
    :param value_label: int, default 0 or 1. If set to 1,
    """

    def __init__(self, interest=0.0001, start="2012-01-01", value_label=0):
        self.interest = interest
        start = convert_date(start)
        self.start = start
        super().__init__(
            "mf", value_label=value_label, fetch=False, save=False, path="nobackend"
        )  #  cashinfo

    def _basic_init(self):
        self.name = "coin"
        self.rate = 0
        datel = list(
            pd.date_range(dt.datetime.strftime(self.start, "%Y-%m-%d"), yesterdaydash())
        )
        valuel = []
        for i, date in enumerate(datel):
            valuel.append((1 + self.interest) ** i)
        dfdict = {
            "date": datel,
            "netvalue": valuel,
            "totvalue": valuel,
            "comment": [0 for _ in datel],
        }
        df = pd.DataFrame(data=dfdict)
        self.price = df[df["date"].isin(opendate)]


class mfundinfo(basicinfo):
    """


    :param code: string of six digitals, code of real monetnary fund
    :param round_label: int, default 0 or 1, label to the different round scheme of shares, reserved for fundinfo class.
    :param value_label: int, default 0 or 1. 1
    :param fetch: boolean, when open the fetch option, the class will try fetching from local files first in the init
    :param save: boolean, when open the save option, automatically save the class to files
    :param path: string, the file path prefix of IO
    :param form: string, the format of IO, options including: 'csv'

    """

    def __init__(
        self,
        code,
        round_label=0,
        value_label=0,
        fetch=False,
        save=False,
        path="",
        form="csv",
    ):
        if code.startswith("M") and code[1:].isdigit():
            code = code[1:]
        code = code.zfill(6)
        self._url = "http://fund.eastmoney.com/pingzhongdata/" + code + ".js"
        self.rate = 0
        super().__init__(
            code,
            fetch=fetch,
            save=save,
            path=path,
            form=form,
            round_label=round_label,
            value_label=value_label,
        )

    def _basic_init(self):
        self._page = rget(self._url)
        if self._page.text[:800].find("Data_fundSharesPositions") >= 0:
            raise FundTypeError("This code seems to be a fund, use fundinfo instead")
        l = eval(
            re.match(
                r"[\s\S]*Data_millionCopiesIncome = ([^;]*);[\s\S]*", self._page.text
            ).groups()[0]
        )
        self.name = re.match(
            r"[\s\S]*fS_name = \"([^;]*)\";[\s\S]*", self._page.text
        ).groups()[0]
        tz_bj = dt.timezone(dt.timedelta(hours=8))
        datel = [
            dt.datetime.fromtimestamp(int(d[0]) / 1e3, tz=tz_bj).replace(tzinfo=None)
            for d in l
        ]
        ratel = [float(d[1]) for d in l]
        netvalue = [1]
        for dailyrate in ratel:
            netvalue.append(netvalue[-1] * (1 + dailyrate * 1e-4))
        netvalue.remove(1)

        df = pd.DataFrame(
            data={
                "date": datel,
                "netvalue": netvalue,
                "totvalue": netvalue,
                "comment": [0 for _ in datel],
            }
        )
        df = df[df["date"].isin(opendate)]
        if len(df) == 0:
            raise ParserFailure("no price table for %s" % self.code)
        df = df.reset_index(drop=True)
        self.price = df[df["date"] <= yesterdaydash()]

    def _save_csv(self, path):
        """
        save the information and pricetable into path+code.csv, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  string of folder path
        """
        df = pd.DataFrame(
            [[0, 0, self.name, 0]], columns=["date", "netvalue", "comment", "totvalue"]
        )
        df = df.append(self.price, ignore_index=True, sort=True)
        df.sort_index(axis=1).to_csv(
            path + self.code + ".csv", index=False, date_format="%Y-%m-%d"
        )

    def _fetch_csv(self, path):
        """
        fetch the information and pricetable from path+code.csv, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  string of folder path
        """
        try:
            content = pd.read_csv(path + self.code + ".csv")
            pricetable = content.iloc[1:]
            datel = list(pd.to_datetime(pricetable.date))
            self.price = pricetable[["netvalue", "totvalue", "comment"]]
            self.price["date"] = datel
            self.name = content.iloc[0].comment
        except FileNotFoundError as e:
            # print('no saved copy of %s' % self.code)
            raise e

    def _save_sql(self, path):
        """
        save the information and pricetable into sql, not recommend to use manually,
        just set the save label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        s = json.dumps({"name": self.name})
        df = pd.DataFrame(
            [[pd.Timestamp("1990-01-01"), 0, s, 0]],
            columns=["date", "netvalue", "comment", "totvalue"],
        )
        df = df.append(self.price, ignore_index=True, sort=True)
        df.sort_index(axis=1).to_sql(
            "xa" + self.code, con=path, if_exists="replace", index=False
        )

    def _fetch_sql(self, path):
        """
        fetch the information and pricetable from sql, not recommend to use manually,
        just set the fetch label to be true when init the object

        :param path:  engine object from sqlalchemy
        """
        try:
            content = pd.read_sql("xa" + self.code, path)
            pricetable = content.iloc[1:]
            commentl = [float(com) for com in pricetable.comment]
            self.price = pricetable[["date", "netvalue", "totvalue"]]
            self.price["comment"] = commentl
            self.name = json.loads(content.iloc[0].comment)["name"]
        except exc.ProgrammingError as e:
            # print('no saved copy of %s' % self.code)
            raise e

    def update(self):
        """
        function to incrementally update the pricetable after fetch the old one
        """
        lastdate = self.price.iloc[-1].date
        startvalue = self.price.iloc[-1].totvalue
        diffdays = (yesterdayobj() - lastdate).days
        if diffdays == 0:
            return None
        self._updateurl = (
            "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
            + self.code
            + "&page=1&per=1"
        )
        con = rget(self._updateurl)
        soup = BeautifulSoup(con.text, "lxml")
        items = soup.findAll("td")
        if dt.datetime.strptime(str(items[0].string), "%Y-%m-%d") == today_obj():
            diffdays += 1
        if diffdays <= 10:
            # caution: there may be today data!! then a day gap will be in table
            self._updateurl = (
                "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
                + self.code
                + "&page=1&per="
                + str(diffdays)
            )
            con = rget(self._updateurl)
            soup = BeautifulSoup(con.text, "lxml")
            items = soup.findAll("td")
        elif (
            diffdays > 10
        ):  ## there is a 20 item per page limit in the API, so to be safe, we query each page by 10 items only
            items = []
            for pg in range(1, int(diffdays / 10) + 2):
                self._updateurl = (
                    "http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code="
                    + self.code
                    + "&page="
                    + str(pg)
                    + "&per=10"
                )
                con = rget(self._updateurl)
                soup = BeautifulSoup(con.text, "lxml")
                items.extend(soup.findAll("td"))
        else:
            raise TradeBehaviorError(
                "Weird incremental update: the saved copy has future records"
            )

        date = []
        earnrate = []
        comment = []
        for i in range(int(len(items) / 6)):
            ts = pd.Timestamp(str(items[6 * i].string))
            if (ts - lastdate).days > 0:
                date.append(ts)
                earnrate.append(float(items[6 * i + 1].string) * 1e-4)
                comment.append(_nfloat(items[6 * i + 5].string))
        date = date[::-1]
        earnrate = earnrate[::-1]
        comment = comment[::-1]
        netvalue = [startvalue]
        for earn in earnrate:
            netvalue.append(netvalue[-1] * (1 + earn))
        netvalue.remove(startvalue)

        df = pd.DataFrame(
            {
                "date": date,
                "netvalue": netvalue,
                "totvalue": netvalue,
                "comment": comment,
            }
        )
        df = df[df["date"].isin(opendate)]
        df = df.reset_index(drop=True)
        df = df[df["date"] <= yesterdayobj()]
        if len(df) != 0:
            self.price = self.price.append(df, ignore_index=True, sort=True)
            return df


FundInfo = fundinfo
MFundInfo = mfundinfo
CashInfo = cashinfo
IndexInfo = indexinfo
