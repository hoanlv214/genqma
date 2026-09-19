// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// @title USYCVault
/// @notice ERC-4626 tokenized vault for Arc Testnet USDC. Share price grows when the owner calls fundYield() to top up accrued yield. Projective 5.0% APY tracking is available via projectedYield().
/// @dev Shares use 6 decimals to match USDC. Vault solvency/share math is based on real on-chain USDC balance.
contract USYCVault is ERC20, ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    uint256 public constant APY_RATE = 5_000; // 5.0% when divided by APY_RATE_SCALE
    uint256 public constant APY_RATE_SCALE = 100_000;
    uint256 public constant YEAR = 365 days;
    uint256 private constant VIRTUAL_ASSETS = 1; // anti-inflation offset
    uint256 private constant VIRTUAL_SHARES = 1; // anti-inflation offset

    IERC20 public constant UNDERLYING_ASSET = IERC20(0x3600000000000000000000000000000000000000);

    uint256 public lastAccrualTimestamp;
    uint256 public totalPrincipal;

    error ZeroAmount();
    error ZeroAddress();
    error ZeroShares();
    error ZeroAssets();

    event Deposit(address indexed caller, address indexed owner, uint256 assets, uint256 shares);
    event Withdraw(address indexed caller, address indexed receiver, address indexed owner, uint256 assets, uint256 shares);
    event YieldAccrued(uint256 newTotalAssets, uint256 timestamp);
    event YieldFunded(address indexed funder, uint256 assets);

    constructor(address initialOwner) ERC20("Hashnote USYC Yield Vault", "yvUSYC") Ownable(initialOwner) {
        if (initialOwner == address(0)) revert ZeroAddress();
        lastAccrualTimestamp = block.timestamp;
    }

    /// @notice Returns the underlying vault asset (USDC on Arc Testnet).
    function asset() external pure returns (address) {
        return address(UNDERLYING_ASSET);
    }

    /// @notice Share token decimals, matched to underlying USDC decimals.
    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /// @notice Returns total managed assets based on real on-chain USDC held by the vault.
    function totalAssets() public view returns (uint256) {
        return UNDERLYING_ASSET.balanceOf(address(this));
    }

    /// @notice Converts an amount of assets to shares, rounding down.
    function convertToShares(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, false, totalAssets(), totalSupply());
    }

    /// @notice Converts an amount of shares to assets, rounding down.
    function convertToAssets(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, false, totalAssets(), totalSupply());
    }

    /// @notice Preview shares minted by a deposit of `assets`, rounding down.
    function previewDeposit(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, false, totalAssets(), totalSupply());
    }

    /// @notice Preview assets required to mint `shares`, rounding up.
    function previewMint(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, true, totalAssets(), totalSupply());
    }

    /// @notice Preview shares required to withdraw `assets`, rounding up.
    function previewWithdraw(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, true, totalAssets(), totalSupply());
    }

    /// @notice Preview assets returned by redeeming `shares`, rounding down.
    function previewRedeem(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, false, totalAssets(), totalSupply());
    }

    /// @notice Maximum assets that may be deposited for `receiver`.
    function maxDeposit(address) external pure returns (uint256) {
        return type(uint256).max;
    }

    /// @notice Maximum shares that may be minted for `receiver`.
    function maxMint(address) external pure returns (uint256) {
        return type(uint256).max;
    }

    /// @notice Maximum assets that may be withdrawn by `owner`.
    function maxWithdraw(address owner) public view returns (uint256) {
        uint256 ownerAssets = convertToAssets(balanceOf(owner));
        uint256 vaultAssets = totalAssets();
        return ownerAssets < vaultAssets ? ownerAssets : vaultAssets;
    }

    /// @notice Maximum shares that may be redeemed by `owner`.
    function maxRedeem(address owner) public view returns (uint256) {
        return balanceOf(owner);
    }

    /// @notice Deposit `assets` USDC and mint vault shares to `receiver`.
    function deposit(uint256 assets, address receiver) public nonReentrant returns (uint256 shares) {
        if (assets == 0) revert ZeroAmount();
        if (receiver == address(0)) revert ZeroAddress();

        _accrueYield();

        uint256 cachedTotalAssets = totalAssets();
        shares = _convertToShares(assets, false, cachedTotalAssets, totalSupply());
        if (shares < 1) revert ZeroShares();

        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        _mint(receiver, shares);

        totalPrincipal += assets;

        emit Deposit(msg.sender, receiver, assets, shares);
    }

    /// @notice Mint `shares` to `receiver` by depositing required assets.
    function mint(uint256 shares, address receiver) public nonReentrant returns (uint256 assets) {
        if (shares == 0) revert ZeroAmount();
        if (receiver == address(0)) revert ZeroAddress();

        _accrueYield();

        uint256 cachedTotalAssets = totalAssets();
        assets = _convertToAssets(shares, true, cachedTotalAssets, totalSupply());
        if (assets < 1) revert ZeroAssets();

        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        _mint(receiver, shares);

        totalPrincipal += assets;

        emit Deposit(msg.sender, receiver, assets, shares);
    }

    /// @notice Withdraw exact `assets` to `receiver`, burning owner shares (rounded up).
    function withdraw(uint256 assets, address receiver, address owner) public nonReentrant returns (uint256 shares) {
        if (assets == 0) revert ZeroAmount();
        if (receiver == address(0) || owner == address(0)) revert ZeroAddress();

        _accrueYield();

        uint256 cachedTotalAssets = totalAssets();
        shares = _convertToShares(assets, true, cachedTotalAssets, totalSupply());
        if (shares < 1) revert ZeroShares();

        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, shares);
        }

        _burn(owner, shares);
        if (totalPrincipal >= assets) {
            totalPrincipal -= assets;
        } else {
            totalPrincipal = 0;
        }
        UNDERLYING_ASSET.safeTransfer(receiver, assets);

        emit Withdraw(msg.sender, receiver, owner, assets, shares);
    }

    /// @notice Redeem `shares` from `owner` and send resulting assets to `receiver`.
    function redeem(uint256 shares, address receiver, address owner) public nonReentrant returns (uint256 assets) {
        if (shares == 0) revert ZeroAmount();
        if (receiver == address(0) || owner == address(0)) revert ZeroAddress();

        _accrueYield();

        uint256 cachedTotalAssets = totalAssets();
        assets = _convertToAssets(shares, false, cachedTotalAssets, totalSupply());
        if (assets < 1) revert ZeroAssets();

        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, shares);
        }

        _burn(owner, shares);
        if (totalPrincipal >= assets) {
            totalPrincipal -= assets;
        } else {
            totalPrincipal = 0;
        }
        UNDERLYING_ASSET.safeTransfer(receiver, assets);

        emit Withdraw(msg.sender, receiver, owner, assets, shares);
    }

    /// @notice Alias for deposit used to initialize/fund vault from any account.
    function seedVault(uint256 assets) external returns (uint256 shares) {
        shares = deposit(assets, msg.sender);
    }

    /// @notice Owner tops up realized yield without minting shares, increasing share price for existing holders.
    function fundYield(uint256 assets) external onlyOwner {
        if (assets == 0) revert ZeroAmount();
        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        emit YieldFunded(msg.sender, assets);
    }

    /// @notice Returns expected yield amount for principal over duration using the 5.0% APY model.
    function projectedYield(uint256 principal, uint256 durationSeconds) external pure returns (uint256) {
        if (principal == 0 || durationSeconds == 0) return 0;
        return _accruedAssets(principal, durationSeconds) - principal;
    }

    /// @notice Updates accrual timestamp and emits current on-chain assets for monitoring.
    function accrueYield() external nonReentrant {
        _accrueYield();
    }

    /// @notice Informational tracking only: updates timestamp and emits current asset balance snapshot.
    function _accrueYield() internal {
        lastAccrualTimestamp = block.timestamp;
        emit YieldAccrued(totalAssets(), block.timestamp);
    }

    function _accruedAssets(uint256 principal, uint256 deltaSeconds) internal pure returns (uint256) {
        if (principal == 0 || deltaSeconds == 0) {
            return principal;
        }

        uint256 yieldAmount = (principal * APY_RATE * deltaSeconds) / (APY_RATE_SCALE * YEAR);
        return principal + yieldAmount;
    }

    function _convertToShares(
        uint256 assets,
        bool roundUp,
        uint256 cachedTotalAssets,
        uint256 supply
    ) internal pure returns (uint256) {
        if (assets == 0) return 0;
        if (roundUp) {
            return Math.mulDiv(assets, supply + VIRTUAL_SHARES, cachedTotalAssets + VIRTUAL_ASSETS, Math.Rounding.Ceil);
        }
        return Math.mulDiv(assets, supply + VIRTUAL_SHARES, cachedTotalAssets + VIRTUAL_ASSETS);
    }

    function _convertToAssets(
        uint256 shares,
        bool roundUp,
        uint256 cachedTotalAssets,
        uint256 supply
    ) internal pure returns (uint256) {
        if (shares < 1) return 0;
        if (roundUp) {
            return Math.mulDiv(shares, cachedTotalAssets + VIRTUAL_ASSETS, supply + VIRTUAL_SHARES, Math.Rounding.Ceil);
        }
        return Math.mulDiv(shares, cachedTotalAssets + VIRTUAL_ASSETS, supply + VIRTUAL_SHARES);
    }
}
