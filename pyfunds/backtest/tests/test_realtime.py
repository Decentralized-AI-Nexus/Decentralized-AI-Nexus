import sys

sys.path.insert(0, "../")
import xalpha as xa
import pytest
import pandas as pd

gf = xa.rfundinfo("001469")


def test_rfundinfo():
    gf.info()
    assert gf.code == "001469"

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
def test_review(capsys):
    st1 = xa.policy.buyandhold(gf, start="2018-08-10", end="2019-01-01")
    st2 = xa.policy.scheduled_tune(
        gf,
        totmoney=1000,
        times=pd.date_range("2018-01-01", "2019-01-01", freq="W-MON"),
        piece=[(0.1, 2), (0.15, 1)],
    )
    check = xa.review([st1, st2], ["Plan A", "Plan Z"])
    assert isinstance(check.content, str) == True
    conf = {}
    check.notification(conf)
    captured = capsys.readouterr()
    assert captured.out == "There are no reminders to be sent\n"
    check.content = "a\nb"
    check.notification(conf)
    captured = capsys.readouterr()
    assert captured.out == "The message failed to be sent\n"
