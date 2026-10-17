package com.example.payments;

public class PaymentRecords {

    public record CardPayload(String pan, String expiry, int amountMinor) {} // expect: PCI002

    public static class Legacy {
        private String accountNumber;

        @Override
        public String toString() {                                // expect: PCI002
            return "Legacy[" + accountNumber + "]";
        }
    }
}
