package com.example.payments;

import org.springframework.web.filter.CommonsRequestLoggingFilter;

public class WebConfig {
    CommonsRequestLoggingFilter filter() {
        CommonsRequestLoggingFilter f = new CommonsRequestLoggingFilter();
        f.setIncludePayload(true);                                // expect: PCI003
        return f;
    }
}
