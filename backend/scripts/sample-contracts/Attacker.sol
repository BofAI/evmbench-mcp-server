// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {LendingVault} from "./LendingVault.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title Attacker
 * @notice A contract that attempts to perform a flash loan attack
 * @dev Used for testing flash loan detection mechanism
 */
contract Attacker {
    LendingVault public vault;
    IERC20 public token;

    constructor(address _vault, address _token) {
        vault = LendingVault(_vault);
        token = IERC20(_token);
    }

    /**
     * @notice Attempts a flash loan attack: borrow and repay in same transaction
     * @param borrowAmount Amount to borrow
     */
    function attack(uint256 borrowAmount) external {
        // Approve tokens for repayment (principal + flash loan fee)
        // Flash loan fee is 5% = 50000 basis points / 100000
        // Total needed: borrowAmount + (borrowAmount * 50000 / 100000) = borrowAmount * 1.05
        // Approve 1.1x to be safe
        uint256 flashLoanFee = (borrowAmount * 50000) / 100000;
        uint256 totalNeeded = borrowAmount + flashLoanFee;
        token.approve(address(vault), totalNeeded * 110 / 100);

        // Step 1: Borrow tokens
        vault.borrow(borrowAmount);

        // Step 2: Perform some operation (simulate arbitrage or manipulation)
        // In a real attack, this would involve DEX swaps, price manipulation, etc.
        // For testing, we just hold the tokens briefly

        // Step 3: Repay in the same transaction (this should trigger flash loan detection)
        vault.repay(borrowAmount);

        // Transfer any remaining tokens back to attacker
        uint256 balance = token.balanceOf(address(this));
        if (balance > 0) {
            token.transfer(msg.sender, balance);
        }
    }

    /**
     * @notice Attack with a callback to external contract (simulates more complex attack)
     * @param borrowAmount Amount to borrow
     * @param target Target contract to call
     * @param data Calldata for target contract
     */
    function attackWithCallback(
        uint256 borrowAmount,
        address target,
        bytes calldata data
    ) external {
        // Approve tokens for repayment (principal + flash loan fee)
        uint256 flashLoanFee = (borrowAmount * 50000) / 100000;
        uint256 totalNeeded = borrowAmount + flashLoanFee;
        token.approve(address(vault), totalNeeded * 110 / 100);

        // Borrow tokens
        vault.borrow(borrowAmount);

        // Execute external logic (e.g., DEX swap, price manipulation)
        (bool success, ) = target.call(data);
        require(success, "Callback failed");

        // Repay in same transaction
        vault.repay(borrowAmount);

        // Transfer any remaining tokens back
        uint256 balance = token.balanceOf(address(this));
        if (balance > 0) {
            token.transfer(msg.sender, balance);
        }
    }
}
