package com.example.payments.logging;

import ch.qos.logback.classic.pattern.MessageConverter;
import ch.qos.logback.classic.spi.ILoggingEvent;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Last line of defence: masks anything that looks like a PAN (13-19 digits,
 * optionally separated by spaces or dashes, passing Luhn) in the formatted message.
 * Wired in logback-spring.xml as %maskedMsg. The pci-shield hook stops most leaks
 * at write time; this catches the ones that arrive through objects it can't see.
 */
public class PanMaskingConverter extends MessageConverter {

    private static final Pattern CANDIDATE = Pattern.compile("(?<!\\d)(?:\\d[ -]?){12,18}\\d(?!\\d)");

    @Override
    public String convert(ILoggingEvent event) {
        return maskPans(super.convert(event));
    }

    static String maskPans(String message) {
        if (message == null) {
            return null;
        }
        Matcher m = CANDIDATE.matcher(message);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            String digits = m.group().replaceAll("[ -]", "");
            String replacement = luhn(digits) ? PanMasker.mask(digits) : m.group();
            m.appendReplacement(out, Matcher.quoteReplacement(replacement));
        }
        m.appendTail(out);
        return out.toString();
    }

    static boolean luhn(String digits) {
        int sum = 0;
        boolean dbl = false;
        for (int i = digits.length() - 1; i >= 0; i--) {
            int d = digits.charAt(i) - '0';
            if (dbl) {
                d *= 2;
                if (d > 9) {
                    d -= 9;
                }
            }
            sum += d;
            dbl = !dbl;
        }
        return sum % 10 == 0;
    }
}
