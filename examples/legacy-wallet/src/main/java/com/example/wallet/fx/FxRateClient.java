package com.example.wallet.fx;

/** Vendor FX SDK wrapper. The vendor API returns rates as double; we can't change that. */
public interface FxRateClient {

    /** Units of {@code to} per one unit of {@code from}, e.g. getRate("USD", "EUR") = 0.9213. */
    double getRate(String from, String to);
}
