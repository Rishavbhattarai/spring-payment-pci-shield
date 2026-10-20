package com.example.payments.payment;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "payment")
public class Payment {

    @Id
    private UUID id;

    @Column(nullable = false, precision = 19, scale = 4)
    private BigDecimal amount;

    @Column(nullable = false, length = 3)
    @JdbcTypeCode(SqlTypes.CHAR) // V1 migration: char(3)
    private String currency;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private PaymentStatus status;

    @Column(name = "pan_last4", nullable = false, length = 4)
    @JdbcTypeCode(SqlTypes.CHAR) // V1 migration: char(4)
    private String panLast4;

    @Column(name = "gateway_ref", length = 64)
    private String gatewayRef;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected Payment() {
    }

    public Payment(BigDecimal amount, String currency, String panLast4) {
        this.id = UUID.randomUUID();
        this.amount = amount;
        this.currency = currency;
        this.panLast4 = panLast4;
        this.status = PaymentStatus.PENDING;
        this.createdAt = Instant.now();
    }

    public void captured(String gatewayRef) {
        this.status = PaymentStatus.CAPTURED;
        this.gatewayRef = gatewayRef;
    }

    public void declined() {
        this.status = PaymentStatus.DECLINED;
    }

    public UUID getId() { return id; }
    public BigDecimal getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public PaymentStatus getStatus() { return status; }
    public String getPanLast4() { return panLast4; }
    public String getGatewayRef() { return gatewayRef; }
    public Instant getCreatedAt() { return createdAt; }
}
