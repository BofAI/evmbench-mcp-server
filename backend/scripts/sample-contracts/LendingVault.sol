// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title LendingVault
 * @notice A simplified lending vault with flash loan protection mechanism
 * @dev Implements deposit, borrow, and repay functions with flash loan detection
 */
contract LendingVault {
    using SafeERC20 for IERC20;

    // Token being lent
    IERC20 public immutable underlyingToken;

    // Fee constants (in basis points, where 100000 = 100%)
    uint256 public constant NORMAL_FEE = 1000; // 0.1%
    uint256 public constant FLASH_LOAN_FEE = 50000; // 5%
    uint256 public constant BASIS_POINTS = 100000; // 100%

    // Accounting
    uint256 public totalLiquidity;
    mapping(address => uint256) public userBalances;
    mapping(address => uint256) public borrowedAmount;

    // Flash loan guard tracking
    mapping(address => uint256) public lastActionBlock;
    mapping(address => bool) public hasBorrowedInBlock;

    // Events
    event Deposit(address indexed user, uint256 amount);
    event Borrow(address indexed user, uint256 amount);
    event Repay(address indexed user, uint256 amount, uint256 fee, bool isFlashLoan);

    /**
     * @notice Constructor
     * @param _underlyingToken Address of the ERC20 token to be lent
     */
    constructor(address _underlyingToken) {
        underlyingToken = IERC20(_underlyingToken);
    }

    /**
     * @notice Deposit tokens into the vault
     * @param amount Amount of tokens to deposit
     */
    function deposit(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");

        // Transfer tokens from user to vault
        underlyingToken.safeTransferFrom(msg.sender, address(this), amount);

        // Update accounting
        totalLiquidity += amount;
        userBalances[msg.sender] += amount;

        emit Deposit(msg.sender, amount);
    }

    /**
     * @notice Borrow tokens from the vault
     * @param amount Amount of tokens to borrow
     */
    function borrow(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");
        require(amount <= totalLiquidity, "Insufficient liquidity");
        require(userBalances[msg.sender] >= amount, "Insufficient deposit balance");

        // Update accounting
        borrowedAmount[msg.sender] += amount;
        totalLiquidity -= amount;

        // Track block for flash loan detection
        lastActionBlock[msg.sender] = block.number;
        hasBorrowedInBlock[msg.sender] = true;

        // Transfer tokens to user
        underlyingToken.safeTransfer(msg.sender, amount);

        emit Borrow(msg.sender, amount);
    }

    /**
     * @notice Repay borrowed tokens
     * @param amount Amount of tokens to repay (principal only, fee will be added)
     */
    function repay(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");
        require(borrowedAmount[msg.sender] >= amount, "Repay amount exceeds borrowed amount");

        // Detect flash loan: check if borrow and repay happened in same block
        bool isFlashLoan = hasBorrowedInBlock[msg.sender] && 
                          lastActionBlock[msg.sender] == block.number;

        // Calculate fee based on flash loan detection
        uint256 feeRate = isFlashLoan ? FLASH_LOAN_FEE : NORMAL_FEE;
        uint256 fee = (amount * feeRate) / BASIS_POINTS;

        // Total amount to transfer (principal + fee)
        uint256 totalAmount = amount + fee;

        // Transfer tokens from user (principal + fee)
        underlyingToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        // Update accounting
        borrowedAmount[msg.sender] -= amount;
        totalLiquidity += amount; // Return principal to liquidity
        totalLiquidity += fee; // Add fee as profit for liquidity providers

        // Reset flash loan tracking flag
        hasBorrowedInBlock[msg.sender] = false;

        emit Repay(msg.sender, amount, fee, isFlashLoan);
    }

    /**
     * @notice Get the current fee rate for a user based on their borrowing status
     * @param user Address to check
     * @return feeRate The fee rate in basis points
     */
    function getFeeRate(address user) external view returns (uint256 feeRate) {
        bool isFlashLoan = hasBorrowedInBlock[user] && 
                          lastActionBlock[user] == block.number;
        return isFlashLoan ? FLASH_LOAN_FEE : NORMAL_FEE;
    }
}
