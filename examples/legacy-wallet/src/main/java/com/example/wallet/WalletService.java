package com.example.wallet;

import com.example.wallet.psp.PspClient;
import java.math.BigDecimal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class WalletService {

    private final WalletRepository wallets;
    private final PspClient psp;

    @Transactional
    public Wallet topUp(Long walletId, BigDecimal amount) {
        Wallet wallet = wallets.findById(walletId).orElseThrow();
        String chargeId = psp.chargeToken(wallet.getCardToken(), amount, wallet.getCurrency());
        wallet.setBalance(wallet.getBalance().add(amount));
        log.info("wallet {} topped up by {} {} (charge {})", walletId, amount, wallet.getCurrency(), chargeId);
        return wallet;
    }
}
