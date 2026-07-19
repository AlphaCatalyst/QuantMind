# Tushare Data Contract v1

Authority and identities are recorded in `TUSHARE_AUTHORITY_V1.json` and
governed by ADR-0011.

## Stored inputs

- `stock_basic`: code, exchange, list status/date and delist date for PIT
  eligibility.
- `trade_cal`: SSE open sessions and previous session.
- `daily`: raw OHLC, pre-close, volume and amount for the locked 500 only.
- `adj_factor`: contemporaneous adjustment factor for the locked 500 only.
- `daily_basic`: turnover, `circ_mv` and `total_mv` for the locked 500; the
  only full-market history is the 20 selection cross-sections.
- `index_daily`: raw CSI300 OHLC, pre-close, volume and amount.

All large tables are Parquet with Zstandard compression. Raw requests and
responses do not contain or persist credentials. No complete full-market
history, duplicate CSV, dynamically rebased adjusted-price copy, or 500-stock
Qlib duplicate exists.

## Normalization and Feature contract

`adjusted_{open,high,low,close} = raw_{open,high,low,close} * adj_factor`.
The following are computed on each complete continuous symbol series before
date slicing, with no forward/back fill or zero fill:

- `mom_ret_1d`: one-session adjusted-close return.
- `liq_volume_ratio_5`: raw volume divided by its five-session mean,
  `min_periods=5`.
- `style_beta_20`: population rolling covariance of stock and CSI300 returns
  divided by population rolling CSI300 variance, `min_periods=20`.
- `style_idio_vol_20`: population rolling standard deviation of
  `stock_return - beta20 * market_return`, `min_periods=20`; theoretical
  two-stage warm-up is 39 sessions.

## Label contract

Raw label is `adjusted_close[T+1] / adjusted_open[T+1] - 1`. A sample receives
weight zero if the next quote is missing, volume is not positive, or the next
session is conservatively classified as locked at a price limit. Model label
is a per-date five-MAD winsorization followed by population z-score. Raw label,
model label and sample weight are distinct fields.

## Qlib view

The Qlib view contains exactly the fixed 100 equities plus CSI300 as a
non-universe benchmark. It exposes raw prices, factor, adjusted close,
tradability, four Features and Label fields. The 2026-06-24 calendar entry is
an empty boundary sentinel; research data ends 2026-06-23. Qlib is a consumer
view and never the data authority.
