package com.example.payments.payment;

import static org.assertj.core.api.Assertions.assertThat;

import com.example.payments.gateway.FakePaymentGateway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers(disabledWithoutDocker = true)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class PaymentApiIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired
    TestRestTemplate http;

    @Autowired
    FakePaymentGateway gateway;

    static final String BODY = """
            {"cardNumber":"4242424242424242","expiry":"12/30","cvv":"123","amount":"19.99","currency":"USD"}
            """;

    @BeforeEach
    void reset() {
        gateway.reset();
    }

    @Test
    void chargesAndReadsBack() {
        ResponseEntity<String> created = post(BODY);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(created.getBody()).contains("\"status\":\"CAPTURED\"").contains("\"panLast4\":\"4242\"")
                .doesNotContain("4242424242424242");
        assertThat(gateway.chargeCount()).isEqualTo(1);
    }

    /**
     * Documents the naive baseline: a client retry after a timeout charges twice.
     * Flip this to isEqualTo(1) once the endpoint is idempotent (see the
     * idempotent-endpoint-scaffold skill).
     */
    @Test
    void naiveBaselineChargesTwiceOnRetry() {
        post(BODY);
        post(BODY);
        assertThat(gateway.chargeCount()).isEqualTo(2);
    }

    private ResponseEntity<String> post(String body) {
        var headers = new org.springframework.http.HttpHeaders();
        headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
        return http.postForEntity("/payments", new org.springframework.http.HttpEntity<>(body, headers), String.class);
    }
}
