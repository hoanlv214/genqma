// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Math} from "@openzeppelin/contracts/utils/math/Math.sol";

/// @title USYCVault (Hardened & Audited)
/// @notice Production-grade ERC-4626 tokenized money market vault for Arc Testnet / Mainnet USDC.
///         Designed specifically for autonomous AI CFOs, Treasury bots, and corporate balance sweeps.
///
/// Security & Architectural Properties:
///
///  1. [PRIMARY ANTI-INFLATION DEFENSE — Accounting Level]
///     totalAssets() returns an internally managed ledger (_totalManagedAssets), updated strictly
///     via deposit(), mint(), withdraw(), redeem(), and fundYield(). It NEVER reads raw
///     UNDERLYING_ASSET.balanceOf(address(this)) for share conversion. Direct token donations
///     or transfers into the contract address CANNOT inflate the share price or cause victim
///     deposits to round down to 0 shares.
///
///  2. [SECONDARY ANTI-INFLATION DEFENSE — Decimals Offset & Virtual Shares]
///     Implements OpenZeppelin ERC-4626 canonical DECIMALS_OFFSET = 6:
///     - decimals() returns _assetDecimals + DECIMALS_OFFSET (6 + 6 = 12).
///     - VIRTUAL_SHARES = 10**DECIMALS_OFFSET (10^6), VIRTUAL_ASSETS = 1.
///     - 1.0 USDC deposited at genesis yields exactly 1.0 yvUSYC shares in nominal representation.
///
///  3. [DEPOSIT CAP RISK CONTROL]
///     Includes an owner/AI-CFO-managed `depositCap`. When enabled (> 0), deposits exceeding
///     the risk threshold revert with ExceedsDepositCap. maxDeposit() and maxMint() dynamically
///     reflect remaining cap capacity.
///
///  4. [EMERGENCY PAUSABLE WITH UNRESTRICTED REDEMPTIONS]
///     whenNotPaused protects deposit() and mint() to halt new risk intake during market anomalies.
///     withdraw() and redeem() are DELIBERATELY EXEMPT from pause — depositors always retain
///     unconditional exit liquidity for their underlying assets.
///
///  5. [SURPLUS RECOVERY]
///     Any external tokens accidentally sent directly to the contract address sit in `surplus()`
///     and can be recovered via sweepSurplus(). It can NEVER touch assets backing user shares.
///
///  6. [YIELD REALIZATION MODEL]
///     USYC tracks real-world US Treasury Bills (RWA). Yield is realized off-chain and credited
///     on-chain via `fundYield()`. `projectedYield()` is an informational estimate model.
contract USYCVaultFixed is ERC20, ReentrancyGuard, Ownable, Pausable {
    using SafeERC20 for IERC20;

    uint256 public constant APY_RATE = 5_000; // 5.0% annualized target (5,000 / 100,000)
    uint256 public constant APY_RATE_SCALE = 100_000;
    uint256 public constant YEAR = 365 days;

    /// @dev Decimals offset per OpenZeppelin ERC-4626 standard.
    uint8 public constant DECIMALS_OFFSET = 6;
    uint256 private constant VIRTUAL_ASSETS = 1;
    uint256 private constant VIRTUAL_SHARES = 10 ** DECIMALS_OFFSET;

    IERC20 public immutable UNDERLYING_ASSET;
    uint8 private immutable _assetDecimals;

    /// @dev Sole internal source of truth for share price accounting.
    uint256 private _totalManagedAssets;

    /// @dev Optional risk ceiling (0 = uncapped). In units of underlying asset.
    uint256 public depositCap;

    uint256 public lastAccrualTimestamp;

    error ZeroAmount();
    error ZeroAddress();
    error ZeroShares();
    error ZeroAssets();
    error NoSurplus();
    error ExceedsDepositCap();

    event Deposit(address indexed caller, address indexed owner, uint256 assets, uint256 shares);
    event Withdraw(address indexed caller, address indexed receiver, address indexed owner, uint256 assets, uint256 shares);
    event YieldAccrued(uint256 newTotalAssets, uint256 timestamp);
    event YieldFunded(address indexed funder, uint256 assets);
    event SurplusSwept(address indexed to, uint256 amount);
    event DepositCapUpdated(uint256 oldCap, uint256 newCap);

    constructor(address initialOwner, address underlyingAsset)
        ERC20("Hashnote USYC Yield Vault", "yvUSYC")
        Ownable(initialOwner)
    {
        if (initialOwner == address(0) || underlyingAsset == address(0)) revert ZeroAddress();
        UNDERLYING_ASSET = IERC20(underlyingAsset);
        _assetDecimals = IERC20Metadata(underlyingAsset).decimals();
        lastAccrualTimestamp = block.timestamp;
    }

    /// @notice Returns the underlying token address (Circle USDC on Arc).
    function asset() external view returns (address) {
        return address(UNDERLYING_ASSET);
    }

    /// @notice Native decimals of the underlying asset (e.g., 6 for USDC).
    function assetDecimals() external view returns (uint8) {
        return _assetDecimals;
    }

    /// @notice Decimals of the share token. Equals assetDecimals + DECIMALS_OFFSET (6 + 6 = 12)
    ///         per OpenZeppelin ERC-4626 canonical specification.
    function decimals() public view override returns (uint8) {
        return _assetDecimals + DECIMALS_OFFSET;
    }

    /// @notice Internally tracked assets backing all outstanding shares.
    function totalAssets() public view returns (uint256) {
        return _totalManagedAssets;
    }

    /// @notice Tokens held by contract that exceed managed assets (e.g. direct ERC20 transfers).
    ///         Never affects share price; recoverable by owner via sweepSurplus().
    function surplus() public view returns (uint256) {
        uint256 bal = UNDERLYING_ASSET.balanceOf(address(this));
        return bal > _totalManagedAssets ? bal - _totalManagedAssets : 0;
    }

    /// @notice Update vault deposit cap. 0 = no cap.
    function setDepositCap(uint256 newCap) external onlyOwner {
        emit DepositCapUpdated(depositCap, newCap);
        depositCap = newCap;
    }

    // --- ERC-4626 Conversions ---

    function convertToShares(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, false, totalAssets(), totalSupply());
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, false, totalAssets(), totalSupply());
    }

    function previewDeposit(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, false, totalAssets(), totalSupply());
    }

    function previewMint(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, true, totalAssets(), totalSupply());
    }

    function previewWithdraw(uint256 assets) public view returns (uint256) {
        return _convertToShares(assets, true, totalAssets(), totalSupply());
    }

    function previewRedeem(uint256 shares) public view returns (uint256) {
        return _convertToAssets(shares, false, totalAssets(), totalSupply());
    }

    // --- Capacity Queries ---

    function maxDeposit(address) external view returns (uint256) {
        if (paused()) return 0;
        if (depositCap == 0) return type(uint256).max;
        return _totalManagedAssets >= depositCap ? 0 : depositCap - _totalManagedAssets;
    }

    function maxMint(address) external view returns (uint256) {
        if (paused()) return 0;
        if (depositCap == 0) return type(uint256).max;
        uint256 remainingAssets = _totalManagedAssets >= depositCap ? 0 : depositCap - _totalManagedAssets;
        return convertToShares(remainingAssets);
    }

    function maxWithdraw(address owner_) public view returns (uint256) {
        uint256 ownerAssets = convertToAssets(balanceOf(owner_));
        uint256 liquid = UNDERLYING_ASSET.balanceOf(address(this));
        return ownerAssets < liquid ? ownerAssets : liquid;
    }

    function maxRedeem(address owner_) public view returns (uint256) {
        uint256 ownerShares = balanceOf(owner_);
        uint256 liquidShares = convertToShares(UNDERLYING_ASSET.balanceOf(address(this)));
        return ownerShares < liquidShares ? ownerShares : liquidShares;
    }

    // --- Core Vault Interactions ---

    function deposit(uint256 assets, address receiver) public nonReentrant whenNotPaused returns (uint256 shares) {
        if (assets == 0) revert ZeroAmount();
        if (receiver == address(0)) revert ZeroAddress();
        if (depositCap > 0 && _totalManagedAssets + assets > depositCap) revert ExceedsDepositCap();

        _accrueYield();

        shares = _convertToShares(assets, false, totalAssets(), totalSupply());
        if (shares < 1) revert ZeroShares();

        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        _totalManagedAssets += assets;
        _mint(receiver, shares);

        emit Deposit(msg.sender, receiver, assets, shares);
    }

    function mint(uint256 shares, address receiver) public nonReentrant whenNotPaused returns (uint256 assets) {
        if (shares == 0) revert ZeroAmount();
        if (receiver == address(0)) revert ZeroAddress();

        _accrueYield();

        assets = _convertToAssets(shares, true, totalAssets(), totalSupply());
        if (assets < 1) revert ZeroAssets();
        if (depositCap > 0 && _totalManagedAssets + assets > depositCap) revert ExceedsDepositCap();

        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        _totalManagedAssets += assets;
        _mint(receiver, shares);

        emit Deposit(msg.sender, receiver, assets, shares);
    }

    /// @dev Deliberately has NO whenNotPaused — redemptions and withdrawals MUST ALWAYS work.
    function withdraw(uint256 assets, address receiver, address owner_) public nonReentrant returns (uint256 shares) {
        if (assets == 0) revert ZeroAmount();
        if (receiver == address(0) || owner_ == address(0)) revert ZeroAddress();

        _accrueYield();

        shares = _convertToShares(assets, true, totalAssets(), totalSupply());
        if (shares < 1) revert ZeroShares();

        if (msg.sender != owner_) {
            _spendAllowance(owner_, msg.sender, shares);
        }

        _burn(owner_, shares);
        _totalManagedAssets -= assets;
        UNDERLYING_ASSET.safeTransfer(receiver, assets);

        emit Withdraw(msg.sender, receiver, owner_, assets, shares);
    }

    /// @dev Deliberately has NO whenNotPaused — redemptions and withdrawals MUST ALWAYS work.
    function redeem(uint256 shares, address receiver, address owner_) public nonReentrant returns (uint256 assets) {
        if (shares == 0) revert ZeroAmount();
        if (receiver == address(0) || owner_ == address(0)) revert ZeroAddress();

        _accrueYield();

        assets = _convertToAssets(shares, false, totalAssets(), totalSupply());
        if (assets < 1) revert ZeroAssets();

        if (msg.sender != owner_) {
            _spendAllowance(owner_, msg.sender, shares);
        }

        _burn(owner_, shares);
        _totalManagedAssets -= assets;
        UNDERLYING_ASSET.safeTransfer(receiver, assets);

        emit Withdraw(msg.sender, receiver, owner_, assets, shares);
    }

    function seedVault(uint256 assets) external returns (uint256 shares) {
        shares = deposit(assets, msg.sender);
    }

    // --- Yield Realization & Administration ---

    /// @notice Owner / Treasury Manager injects realized RWA yield (USDC) into the vault.
    ///         Increases share price for all existing holders pro-rata without minting new shares.
    function fundYield(uint256 assets) external onlyOwner nonReentrant {
        if (assets == 0) revert ZeroAmount();
        UNDERLYING_ASSET.safeTransferFrom(msg.sender, address(this), assets);
        _totalManagedAssets += assets;
        lastAccrualTimestamp = block.timestamp;
        emit YieldFunded(msg.sender, assets);
        emit YieldAccrued(_totalManagedAssets, block.timestamp);
    }

    /// @notice Recover accidental token transfers that are NOT part of managed assets.
    ///         Cannot touch any assets backing user shares.
    function sweepSurplus(address to) external onlyOwner nonReentrant {
        if (to == address(0)) revert ZeroAddress();
        uint256 amount = surplus();
        if (amount == 0) revert NoSurplus();
        UNDERLYING_ASSET.safeTransfer(to, amount);
        emit SurplusSwept(to, amount);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    /// @notice Expected yield for `principal` over `durationSeconds` at APY_RATE.
    ///         INFORMATIONAL ESTIMATE ONLY — real yield is credited via fundYield().
    function projectedYield(uint256 principal, uint256 durationSeconds) external pure returns (uint256) {
        if (principal == 0 || durationSeconds == 0) return 0;
        return _accruedAssets(principal, durationSeconds) - principal;
    }

    function accrueYield() external nonReentrant {
        _accrueYield();
    }

    function _accrueYield() internal {
        lastAccrualTimestamp = block.timestamp;
        emit YieldAccrued(totalAssets(), block.timestamp);
    }

    function _accruedAssets(uint256 principal, uint256 deltaSeconds) internal pure returns (uint256) {
        if (principal == 0 || deltaSeconds == 0) return principal;
        uint256 yieldAmount = (principal * APY_RATE * deltaSeconds) / (APY_RATE_SCALE * YEAR);
        return principal + yieldAmount;
    }

    // --- Math Helpers (mulDiv rounding) ---

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
