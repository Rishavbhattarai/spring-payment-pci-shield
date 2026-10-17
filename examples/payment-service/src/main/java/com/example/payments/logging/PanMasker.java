package com.example.payments.logging;

/** PCI-DSS 3.4 display rule: at most the first 6 and last 4 digits. We show last 4 only. */
public final class PanMasker {

    private PanMasker() {
    }

    public static String mask(String pan) {
        if (pan == null || pan.length() < 4) {
            return "****";
        }
        return "*".repeat(pan.length() - 4) + pan.substring(pan.length() - 4);
    }
}
