package com.example.payments;

public class PaymentRecords {

    public record CardPayload(String pan, String expiry, long amountMinor) {
        @Override
        public String toString() {
            return "CardPayload[pan=" + Masking.last4(pan) + ", amountMinor=" + amountMinor + "]";
        }
    }

    public record Receipt(String id, String maskedPan, long amountMinor) {}

    public static class NoLombok {
        private String accountNumber;
    }
}
