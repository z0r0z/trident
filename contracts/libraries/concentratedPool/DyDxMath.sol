// SPDX-License-Identifier: GPL-3.0-or-later

pragma solidity >=0.8.0;

import "./FullMath.sol";
import "./UnsafeMath.sol";

/// @notice Math library that facilitates ranged liquidity calculations.
library DyDxMath {
    function getDy(
        uint256 liquidity,
        uint256 priceLower,
        uint256 priceUpper,
        bool roundUp
    ) internal pure returns (uint256 dy) {
        unchecked {
            if (roundUp) {
                dy = FullMath.mulDivRoundingUp(liquidity, priceUpper - priceLower, 0x1000000000000000000000000);
            } else {
                dy = FullMath.mulDiv(liquidity, priceUpper - priceLower, 0x1000000000000000000000000);
            }
        }
    }

    function getDx(
        uint256 liquidity,
        uint256 priceLower,
        uint256 priceUpper,
        bool roundUp
    ) internal pure returns (uint256 dx) {
        unchecked {
            if (roundUp) {
                dx = UnsafeMath.divRoundingUp(FullMath.mulDivRoundingUp(liquidity << 96, priceUpper - priceLower, priceUpper), priceLower);
            } else {
                dx = FullMath.mulDiv(liquidity << 96, priceUpper - priceLower, priceUpper) / priceLower;
            }
        }
    }

    function getLiquidityForAmounts(
        uint256 priceLower,
        uint256 priceUpper,
        uint256 currentPrice,
        uint256 dy,
        uint256 dx
    ) internal pure returns (uint256 liquidity) {
        unchecked {
            if (priceUpper <= currentPrice) {
                liquidity = FullMath.mulDiv(dy, 0x1000000000000000000000000, priceUpper - priceLower);
            } else if (currentPrice <= priceLower) {
                liquidity = FullMath.mulDiv(
                    dx,
                    FullMath.mulDiv(priceLower, priceUpper, 0x1000000000000000000000000),
                    priceUpper - priceLower
                );
            } else {
                uint256 liquidity0 = FullMath.mulDiv(
                    dx,
                    FullMath.mulDiv(priceUpper, currentPrice, 0x1000000000000000000000000),
                    priceUpper - currentPrice
                );
                uint256 liquidity1 = FullMath.mulDiv(dy, 0x1000000000000000000000000, currentPrice - priceLower);
                liquidity = liquidity0 < liquidity1 ? liquidity0 : liquidity1;
            }
        }
    }

    function getAmountsForLiquidity(
        uint256 priceLower,
        uint256 priceUpper,
        uint256 currentPrice,
        uint256 liquidityAmount,
        bool roundUp
    ) internal pure returns (uint128 token0amount, uint128 token1amount) {
        if (priceUpper <= currentPrice) {
            /// @dev Only supply `token1` (`token1` is Y).
            token1amount = uint128(DyDxMath.getDy(liquidityAmount, priceLower, priceUpper, roundUp));
        } else if (currentPrice <= priceLower) {
            /// @dev Only supply `token0` (`token0` is X).
            token0amount = uint128(DyDxMath.getDx(liquidityAmount, priceLower, priceUpper, roundUp));
        } else {
            /// @dev Supply both tokens.
            token0amount = uint128(DyDxMath.getDx(liquidityAmount, currentPrice, priceUpper, roundUp));
            token1amount = uint128(DyDxMath.getDy(liquidityAmount, priceLower, currentPrice, roundUp));
        }
    }
}
