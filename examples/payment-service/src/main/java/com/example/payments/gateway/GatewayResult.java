package com.example.payments.gateway;

public record GatewayResult(boolean approved, String reference) {
}
