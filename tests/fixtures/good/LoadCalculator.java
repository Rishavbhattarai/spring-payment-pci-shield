package com.example.scheduler;

// Not payment code: "total" and "balance" here are not money.
public class LoadCalculator {
    private double totalWeight;
    private double balanceFactor;
    private double feeRatio;

    double memoryUsedOfTotalPercentage(long used, long total) {
        double total2 = total;
        return used / total2;
    }
}
