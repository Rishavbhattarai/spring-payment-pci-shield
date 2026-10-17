package com.example.payments;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CheckoutController {

    @PostMapping("/checkout")                                     // expect: IDM001
    public CheckoutResponse checkout(@RequestBody CheckoutRequest request) {
        return null;
    }

    @GetMapping("/checkout/{id}")
    public CheckoutResponse get(String id) {
        return null;
    }
}
