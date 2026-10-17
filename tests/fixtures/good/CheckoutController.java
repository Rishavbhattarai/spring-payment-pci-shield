package com.example.payments;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CheckoutController {

    @PostMapping("/checkout")
    public CheckoutResponse checkout(@RequestHeader("Idempotency-Key") String idempotencyKey,
                                     @RequestBody CheckoutRequest request) {
        return null;
    }
}
