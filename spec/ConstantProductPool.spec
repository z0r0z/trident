/*
    This is a specification file for the verification of ConstantProductPool.sol
    smart contract using the Certora prover. For more information,
	visit: https://www.certora.com/

    This file is run with scripts/verifyConstantProductPool.sol
	Assumptions:
*/

using SimpleBentoBox as bentoBox

////////////////////////////////////////////////////////////////////////////
//                                Methods                                 //
////////////////////////////////////////////////////////////////////////////
/*
    Declaration of methods that are used in the rules. envfree indicate that
    the method is not dependent on the environment (msg.value, msg.sender).
    Methods that are not declared here are assumed to be dependent on env.
*/

methods {
    // ConstantProductPool state variables
    token0() returns (address) envfree
    token1() returns (address) envfree
    reserve0() returns (uint112) envfree
    reserve1() returns (uint112) envfree

    // ConstantProductPool functions
    _balance() returns (uint256 balance0, uint256 balance1) envfree
    transferFrom(address, address, uint256)
    totalSupply() returns (uint256) envfree
    getAmountOutWrapper(address tokenIn, uint256 amountIn) returns (uint256) envfree
    balanceOf(address) returns (uint256) envfree

    // TODO: not working
    // TridentERC20 (permit)
    ecrecover(bytes32 digest, uint8 v, bytes32 r, bytes32 s) 
              returns (address) => NONDET

    // ConstantProductPool (swap, swapWithContext) -> ITridentCallee (tridentCallback)
    tridentCallback(address tokenIn, address tokenOut, uint256 amountIn,
                    uint256 amountOut, bytes data) => NONDET

    // simplification of sqrt
    sqrt(uint256 x) returns (uint256) => DISPATCHER(true) UNRESOLVED

    // bentobox
    bentoBox.balanceOf(address token, address user) returns (uint256) envfree
    bentoBox.transfer(address token, address from, address to, uint256 share)

    // IERC20
    transfer(address recipient, uint256 amount) returns (bool) => DISPATCHER(true) UNRESOLVED
    balanceOf(address account) returns (uint256) => DISPATCHER(true) UNRESOLVED
    tokenBalanceOf(address token, address user) returns (uint256 balance) envfree 

    // MasterDeployer(masterDeployer).barFee()
    barFee() => NONDET
}

////////////////////////////////////////////////////////////////////////////
//                                 Ghost                                  //
////////////////////////////////////////////////////////////////////////////

////////////////////////////////////////////////////////////////////////////
//                               Invariants                               //
////////////////////////////////////////////////////////////////////////////
// REVIEW: This should fail (passing right now)
invariant validityOfTokens()
    token0() != 0 && token1() != 0 &&  token0() != token1()

// REVIEW: This should fail (passing right now)
invariant tokensNotMirin()
    token0() != currentContract && token1() != currentContract

// use 1 and 2 to prove reserveLessThanEqualToBalance
invariant reserveLessThanEqualToBalance()
    reserve0() <= bentoBox.balanceOf(token0(), currentContract) && 
    reserve1() <= bentoBox.balanceOf(token1(), currentContract) {
		preserved {
			requireInvariant validityOfTokens();
		}
	}

invariant integrityOfTotalSupply()
    totalSupply() == 0 => ( reserve0() == 0 && reserve1() == 0 ) {
        preserved burnWrapper(address to ,bool b) with (env e) {
            require e.msg.sender != currentContract;
            require to != currentContract;
            require totalSupply()==0 || balanceOf(e.msg.sender) < totalSupply() + 1000;
        }
        preserved burnSingleWrapper(address tokenOut, address to, bool b) with (env e) {
             require e.msg.sender != currentContract;
            require to != currentContract;
            require totalSupply()==0 || balanceOf(e.msg.sender) < totalSupply() + 1000;
        }
        preserved  swapWrapper(address tokenIn, address recipient, bool unwrapBento) with (env e) {
            requireInvariant reserveLessThanEqualToBalance;
            uint256 amountIn = reserve0()-  bentoBox.balanceOf(token0(), currentContract);
            require tokenIn == token0();
            require amountIn >0  => getAmountOutWrapper(token0(), amountIn) > 0 ;
        }

    }
    
////////////////////////////////////////////////////////////////////////////
//                                 Rules                                  //
////////////////////////////////////////////////////////////////////////////
rule sanity(method f) {
    env e;
    calldataarg args;
    f(e, args);

    assert(false);
}

// Passing
rule noChangeToBalancedPoolAssets(method f) filtered { f ->
                    f.selector != flashSwapWrapper(address, address, bool, uint256, bytes).selector } {
    env e;

    uint256 _balance0;
    uint256 _balance1;

    _balance0, _balance1 = _balance();
    
    validState(true);
    // require that the system has no mirin tokens
    require balanceOf(currentContract) == 0;

    calldataarg args;
    f(e, args);
    
    uint256 balance0_;
    uint256 balance1_;

    balance0_, balance1_ = _balance();

    // post-condition: pool's balances don't change
    assert(_balance0 == balance0_ && _balance1 == balance1_, 
           "pool's balance in BentoBox changed");
}

// Passing
rule afterOpBalanceEqualsReserve(method f) {
    env e;

    validState(false);

    uint256 _balance0;
    uint256 _balance1;

    _balance0, _balance1 = _balance();

    uint256 _reserve0 = reserve0();
    uint256 _reserve1 = reserve1();

    address to;
    address tokenIn;
    address tokenOut;
    address recipient;
    bool unwrapBento;

    require to != currentContract;
    require recipient != currentContract;
    
    if (f.selector == burnWrapper(address, bool).selector) {
        burnWrapper(e, to, unwrapBento);
    } else if (f.selector == burnSingleWrapper(address, address, bool).selector) {
        burnSingleWrapper(e, tokenOut, to, unwrapBento);
    } else if (f.selector == swapWrapper(address, address, bool).selector) {
        swapWrapper(e, tokenIn, recipient, unwrapBento);
    } else {
        calldataarg args;
        f(e, args);
    }

    uint256 balance0_;
    uint256 balance1_;

    balance0_, balance1_ = _balance();

    uint256 reserve0_ = reserve0();
    uint256 reserve1_ = reserve1();

    // (reserve or balances changed before and after the method call) => 
    // (reserve0() == balance0_ && reserve1() == balance1_)
    // reserve can go up or down or the balance doesn't change
    assert((_balance0 != balance0_ || _balance1 != balance1_ ||
            _reserve0 != reserve0_ || _reserve1 != reserve1_) =>
            (reserve0_ == balance0_ && reserve1_ == balance1_),
           "balance doesn't equal reserve after state changing operations");
}

// Passing
rule mintingNotPossibleForBalancedPool() {
    env e;

    require totalSupply() > 0 || ( reserve0() == 0 || reserve1() == 0 ); // REVIEW: failing without this

    validState(true);

    calldataarg args;
    uint256 liquidity = mintWrapper@withrevert(e, args);

    assert(lastReverted, "pool minting on no transfer to pool");
}

// DONE: try optimal liquidity of ratio 1 (Timing out when changed args
// to actual variables to make the msg.sender the same)
// TODO: if works, add another rule that checks that burn gives the money to the correct person
// rule inverseOfMintAndBurn() {
//     env e;

//     // establishing ratio 1 (to simplify)
//     require reserve0() == reserve1();
//     require e.msg.sender != currentContract;

//     uint256 balance0;
//     uint256 balance1;

//     balance0, balance1 = _balance();

//     // stimulating transfer to the pool
//     require reserve0() < balance0 && reserve1() < balance1;
//     uint256 _liquidity0 = balance0 - reserve0();
//     uint256 _liquidity1 = balance1 - reserve1();

//     // making sure that we add optimal liquidity
//     require _liquidity0 == _liquidity1;

//     // uint256 _totalUsertoken0 = tokenBalanceOf(token0(), e.msg.sender) + 
//     //                            bentoBox.balanceOf(token0(), e.msg.sender);
//     // uint256 _totalUsertoken1 = tokenBalanceOf(token1(), e.msg.sender) + 
//     //                            bentoBox.balanceOf(token1(), e.msg.sender);

//     uint256 mirinLiquidity = mintWrapper(e, e.msg.sender);

//     // transfer mirin tokens to the pool
//     transferFrom(e, e.msg.sender, currentContract, mirinLiquidity);

//     uint256 liquidity0_;
//     uint256 liquidity1_;

//     bool unwrapBento;
//     liquidity0_, liquidity1_ = burnWrapper(e, e.msg.sender, unwrapBento);

//     // uint256 totalUsertoken0_ = tokenBalanceOf(token0(), e.msg.sender) + 
//     //                            bentoBox.balanceOf(token0(), e.msg.sender);
//     // uint256 totalUsertoken1_ = tokenBalanceOf(token1(), e.msg.sender) + 
//     //                            bentoBox.balanceOf(token1(), e.msg.sender);

//     // do we instead want to check whether the 'to' user got the funds? (Ask Nurit) -- Yes
//     assert(_liquidity0 == liquidity0_ && _liquidity1 == liquidity1_, 
//            "inverse of mint then burn doesn't hold");
//     // assert(_totalUsertoken0 == totalUsertoken0_ && 
//     //        _totalUsertoken1 == totalUsertoken1_, 
//     //        "user's total balances changed");
// }

// Different way
// rule inverseOfMintAndBurn() {
//     env e;
//     address to;
//     bool unwrapBento;

//     require e.msg.sender != currentContract && to != currentContract;
//     // so that they get the mirin tokens and transfer them back. Also,
//     // when they burn, they get the liquidity back
//     require e.msg.sender == to; 

//     validState(true);

//     uint256 _liquidity0;
//     uint256 _liquidity1;

//     uint256 _totalUsertoken0 = tokenBalanceOf(token0(), e.msg.sender) + 
//                                bentoBox.balanceOf(token0(), e.msg.sender);
//     uint256 _totalUsertoken1 = tokenBalanceOf(token1(), e.msg.sender) + 
//                                bentoBox.balanceOf(token1(), e.msg.sender);

//     // sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, _liquidity0);
//     // sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, _liquidity1);
//     uint256 mirinLiquidity = mintWrapper(e, to);

//     // transfer mirin tokens to the pool
//     transferFrom(e, e.msg.sender, currentContract, mirinLiquidity);

//     uint256 liquidity0_;
//     uint256 liquidity1_;

//     liquidity0_, liquidity1_ = burnWrapper(e, to, unwrapBento);

//     uint256 totalUsertoken0_ = tokenBalanceOf(token0(), e.msg.sender) + 
//                                bentoBox.balanceOf(token0(), e.msg.sender);
//     uint256 totalUsertoken1_ = tokenBalanceOf(token1(), e.msg.sender) + 
//                                bentoBox.balanceOf(token1(), e.msg.sender);

//     assert(_liquidity0 == liquidity0_ && _liquidity1 == liquidity1_, 
//            "inverse of mint then burn doesn't hold");
//     assert(_totalUsertoken0 == totalUsertoken0_ && 
//            _totalUsertoken1 == totalUsertoken1_, 
//            "user's total balances changed");
// }

// TODO: add a rule noChangeToOthersBalances
rule noChangeToOthersBalances(method f) {
    env e;

    address other;
    address to;
    address recepient;

    require other != currentContract && e.msg.sender != other &&
            to != other && recepient != other;

    // recording other's mirin balance
    uint256 _otherMirinBalance = balanceOf(other);

    // recording other's tokens balance
    uint256 _totalOthertoken0 = tokenBalanceOf(token0(), other) + 
                               bentoBox.balanceOf(token0(), other);
    uint256 _totalOthertoken1 = tokenBalanceOf(token1(), other) + 
                               bentoBox.balanceOf(token1(), other);

    bool unwrapBento;
    address tokenIn;
    address tokenOut;

    if (f.selector == mintWrapper(address).selector) {
        mintWrapper(e, to);
    } else if (f.selector == burnWrapper(address, bool).selector) {
        burnWrapper(e, to, unwrapBento);
    } else if (f.selector == burnSingleWrapper(address, address, bool).selector) {
        burnSingleWrapper(e, tokenOut, to, unwrapBento);
    } else if (f.selector == swapWrapper(address, address, bool).selector) {
        swapWrapper(e, tokenIn, recepient, unwrapBento);
    }  else if (f.selector == flashSwapWrapper(address, address, bool, uint256, bytes).selector) {
        calldataarg args;
        flashSwapWrapper(e, args);
    } else {
        calldataarg args;
        f(e, args);
    }

    // recording other's mirin balance
    uint256 otherMirinBalance_ = balanceOf(other);
    
    // recording other's tokens balance
    uint256 totalOthertoken0_ = tokenBalanceOf(token0(), other) + 
                               bentoBox.balanceOf(token0(), other);
    uint256 totalOthertoken1_ = tokenBalanceOf(token1(), other) + 
                               bentoBox.balanceOf(token1(), other);

    assert(_otherMirinBalance == otherMirinBalance_, "other's Mirin balance changed");
    assert(_totalOthertoken0 == totalOthertoken0_, "other's token0 balance changed");
    assert(_totalOthertoken1 == totalOthertoken1_, "other's token1 balance changed");
}

rule burnTokenAdditivity() {
    env e;
    address to;
    bool unwrapBento;
    uint256 mirinLiquidity;

    validState(true);
    // require to != currentContract;
    // REVIEW: require balanceOf(e, currentContract) == 0; (Passing with or without)

    // need to replicate the exact state later on
    storage initState = lastStorage;

    // burn single token
    transferFrom(e, e.msg.sender, currentContract, mirinLiquidity);
    uint256 liquidity0Single = burnSingleWrapper(e, token0(), to, unwrapBento);

    // uint256 _totalUsertoken0 = tokenBalanceOf(token0(), e.msg.sender) + 
    //                            bentoBox.balanceOf(token0(), e.msg.sender);
    // uint256 _totalUsertoken1 = tokenBalanceOf(token1(), e.msg.sender) + 
    //                            bentoBox.balanceOf(token1(), e.msg.sender);

    uint256 liquidity0;
    uint256 liquidity1;

    // burn both tokens
    transferFrom(e, e.msg.sender, currentContract, mirinLiquidity) at initState;
    liquidity0, liquidity1 = burnWrapper(e, to, unwrapBento);

    // swap token1 for token0
    sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, liquidity1);
    uint256 amountOut = swapWrapper(e, token1(), to, unwrapBento);

    // uint256 totalUsertoken0_ = tokenBalanceOf(token0(), e.msg.sender) + 
    //                            bentoBox.balanceOf(token0(), e.msg.sender);
    // uint256 totalUsertoken1_ = tokenBalanceOf(token1(), e.msg.sender) + 
    //                            bentoBox.balanceOf(token1(), e.msg.sender);

    assert(liquidity0Single == liquidity0 + amountOut, "burns not equivalent");
    // assert(_totalUsertoken0 == totalUsertoken0_, "user's token0 changed");
    // assert(_totalUsertoken1 == totalUsertoken1_, "user's token1 changed");
}

rule sameUnderlyingRatioLiquidity(method f) filtered { f -> 
        f.selector == swapWrapper(address, address, bool).selector ||
        f.selector == flashSwapWrapper(address, address, bool, uint256, bytes).selector } {
    env e1;
    env e2;
    env e3;

    // setting the environment constraints
    require e1.block.timestamp < e2.block.timestamp && 
            e2.block.timestamp < e3.block.timestamp;
    // REVIEW: swap is done by someother person (maybe incorrect)
    require e1.msg.sender == e3.msg.sender && e2.msg.sender != e1.msg.sender;

    validState(true);

    require reserve0() / reserve1() == 2;

    uint256 _liquidity0;
    uint256 _liquidity1;

    if (totalSupply() != 0) {
        // user's liquidity for token0 = user's mirinTokens * reserve0 / totalSupply of mirinTokens
        _liquidity0 = balanceOf(e1.msg.sender) * reserve0() / totalSupply();
        // user's liquidity for token1 = user's mirinTokens * reserve0 / totalSupply of mirinTokens
        _liquidity1 = balanceOf(e1.msg.sender) * reserve1() / totalSupply();
    } else {
        _liquidity0 = 0;
        _liquidity1 = 0;
    }

    calldataarg args;
    f(e2, args); // TODO: run with all swaps

    uint256 liquidity0_;
    uint256 liquidity1_;

    if (totalSupply() != 0) {
        // user's liquidity for token0 = user's mirinTokens * reserve0 / totalSupply of mirinTokens
        uint256 liquidity0_ = balanceOf(e3.msg.sender) * reserve0() / totalSupply();
        // user's liquidity for token1 = user's mirinTokens * reserve0 / totalSupply of mirinTokens
        uint256 liquidity1_ = balanceOf(e3.msg.sender) * reserve1() / totalSupply();
    } else {
        liquidity0_ = 0;
        liquidity1_ = 0;
    }
    
    // since swap is taking place, liquidities should be strictly greater
    // TODO: && totalSupply() != 0 not working, counter example when liquidities are 0
    assert((reserve0() / reserve1() == 2) => (_liquidity0 <= liquidity0_ &&
           _liquidity1 <= liquidity1_), "with time liquidities decreased");
}

// Timing out, even with reserve0() / reserve1() == 1
// TODO: all swap methods
// rule multiSwapLessThanSingleSwap() {
//     env e;
//     address to;
//     bool unwrapBento;
//     uint256 liquidity1;
//     uint256 liquidity2;

//     // TODO: liquidity1, liquidity2 can't be 0??? Maybe (to prevent counter examples)
//     require e.msg.sender != currentContract && to != currentContract;

//     validState(true);

//     // need to replicate the exact state later on
//     storage initState = lastStorage;

//     // swap token1 for token0 in two steps
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, liquidity1);
//     uint256 multiAmountOut1 = swapWrapper(e, token1(), to, unwrapBento);
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, liquidity2);
//     uint256 multiAmountOut2 = swapWrapper(e, token1(), to, unwrapBento);

//     // checking for overflows
//     require multiAmountOut1 + multiAmountOut2 <= max_uint256;
//     require liquidity1 + liquidity2 <= max_uint256;

//     // swap token1 for token0 in a single step
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, liquidity1 + liquidity2) at initState; 
//     uint256 singleAmountOut = swapWrapper(e, token1(), to, unwrapBento);

//     // TODO: Mudit wanted strictly greater, but when all amountOuts are 0s we get a counter example
//     assert(singleAmountOut >= multiAmountOut1 + multiAmountOut2, "multiple swaps better than one single swap");
// }

// TODO: add same rule as multiSwapLessThanSingleSwap but using getAmountOut
rule multiLessThanSingleAmountOut() {
    env e;
    uint256 amountInX;
    uint256 amountInY;

    // need to replicate the exact state later on
    storage initState = lastStorage;
    
    uint256 multiAmountOut1 = _getAmountOut(e, amountInX, reserve0(), reserve1());
    require reserve0() + amountInX <= max_uint256;
    uint256 multiAmountOut2 = _getAmountOut(e, amountInY, reserve0() + amountInX, reserve1() - multiAmountOut1);

    // checking for overflows
    require amountInX + amountInY <= max_uint256;

    uint256 singleAmountOut = _getAmountOut(e, amountInX + amountInY, reserve0(), reserve1()) at initState;

    // TODO: Mudit wanted strictly greater
    assert(singleAmountOut >= multiAmountOut1 + multiAmountOut2, "multiple swaps better than one single swap");
}

// Timing out, even with require reserve0() == reserve1();
// rule additivityOfMint() {
//     env e;
//     address to;
//     uint256 x1;
//     uint256 x2;
//     uint256 y1;
//     uint256 y2;

//     // x, y can be 0? Their ratio (they have to be put in the same ratio, right?) 
//     // TODO: require e.msg.sender == to? Or check the assets of 'to'?
//     validState(true);

//     // need to replicate the exact state later on
//     storage initState = lastStorage;

//     // minting in two steps
//     sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, x1);
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, y1);
//     uint256 mirinTwoSteps1 = mintWrapper(e, to);

//     sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, x2);
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, y2);
//     uint256 mirinTwoSteps2 = mintWrapper(e, to);

//     uint256 userMirinBalanceTwoStep = balanceOf(e, e.msg.sender);

//     // checking for overflows
//     require mirinTwoSteps1 + mirinTwoSteps2 <= max_uint256;
//     require x1 + x2 <= max_uint256 && y1 + y2 <= max_uint256;

//     // minting in a single step
//     sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, x1 + x2) at initState;
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, y1 + y2);
//     uint256 mirinSingleStep = mintWrapper(e, to);

//     uint256 userMirinBalanceOneStep = balanceOf(e, e.msg.sender);

//     // TODO: strictly greater than?
//     assert(mirinSingleStep >= mirinTwoSteps1 + mirinTwoSteps2, "multiple mints better than a single mint");
//     assert(userMirinBalanceOneStep >= userMirinBalanceTwoStep, "user received less mirin in one step");
// }

// Timing out, even with ratio 1
// rule mintWithOptimalLiquidity() {
//     env e;
//     address to;

//     uint256 xOptimal;
//     uint256 yOptimal;
//     uint256 x;
//     uint256 y;

//     // require dollarAmount(xOptimal) + dollarAmount(yOptimal) == dollarAmount(x) + dollarAmount(y);
//     require getAmountOutWrapper(e, token0(), yOptimal) + xOptimal == 
//             getAmountOutWrapper(e, token0(), y) + x;

//     require x != y; // requiring that x and y are non optimal

//     require reserve0() == reserve1();
//     require xOptimal == yOptimal; // requiring that these are optimal

//     validState(true);

//     // need to replicate the exact state later on
//     storage initState = lastStorage;

//     // minting with optimal liquidities
//     sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, xOptimal);
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, yOptimal);
//     uint256 mirinOptimal = mintWrapper(e, e.msg.sender);

//     uint256 userMirinBalanceOptimal = balanceOf(e, e.msg.sender);

//     // minting with non-optimal liquidities
//     sinvoke bentoBox.transfer(e, token0(), e.msg.sender, currentContract, x) at initState;
//     sinvoke bentoBox.transfer(e, token1(), e.msg.sender, currentContract, y);
//     uint256 mirinNonOptimal = mintWrapper(e, e.msg.sender);

//     uint256 userMirinBalanceNonOptimal = balanceOf(e, e.msg.sender);

//     // TODO: strictly greater?
//     assert(mirinOptimal >= mirinNonOptimal);
//     assert(userMirinBalanceOptimal >= userMirinBalanceNonOptimal);
// }

// Failing, expected (Sushi needs to fix)
rule zeroCharacteristicsOfGetAmountOut(uint256 _reserve0, uint256 _reserve1) {
    env e;
    uint256 amountIn;
    address tokenIn;

    validState(false);

    // assume token0 to token1
    require tokenIn == token0(); 
    require _reserve0 == reserve0();
    require _reserve0 == reserve1();
    require _reserve0 * _reserve1 >= 1000;
    require MAX_FEE_MINUS_SWAP_FEE(e) <= MAX_FEE(e);

    uint256 amountOut = getAmountOutWrapper(tokenIn, amountIn);

    if (amountIn == 0) {
        assert(amountOut == 0, "amountIn is 0, but amountOut is not 0");
    } else { 
        if (tokenIn == token0() && reserve1() == 0) {
            assert(amountOut == 0, "token1 has no reserves, but amountOut is non-zero");
        } else {
            assert(amountOut > 0);
        }
    }
    /* else if (tokenIn == token1() && reserve0() == 0) {
            assert(amountOut == 0, "token0 has no reserves, but amountOut is non-zero");
        } */ 
}

// Passing
rule maxAmountOut(uint256 _reserve0, uint256 _reserve1) {
    env e;

    uint256 amountIn;
    address tokenIn;

    validState(false);

    require tokenIn == token0(); 
    require _reserve0 == reserve0();
    require _reserve1 == reserve1();
    require _reserve0 > 0 && _reserve1 > 0;
    require MAX_FEE_MINUS_SWAP_FEE(e) <= MAX_FEE(e);

    uint256 amountOut = getAmountOutWrapper(tokenIn, amountIn);
    // mathint maxValue = to_mathint(amountIn) * to_mathint(_reserve1) / to_mathint(_reserve0);
    // assert amountOut <= maxValue;

    assert amountOut <= _reserve1;
}

// Passing (need to check)
rule nonZeroMint() {
    env e;
    address to;

    validState(false);

    require reserve0() > bentoBox.balanceOf(token0(), currentContract) ||
                reserve1() > bentoBox.balanceOf(token1(), currentContract);

    uint256 liquidity = mintWrapper(e, to);

    assert liquidity > 0;
}

////////////////////////////////////////////////////////////////////////////
//                             Helper Methods                             //
////////////////////////////////////////////////////////////////////////////
function validState(bool isBalanced) {
    requireInvariant validityOfTokens();
    requireInvariant tokensNotMirin();

    if (isBalanced) {
        require reserve0() == bentoBox.balanceOf(token0(), currentContract) &&
                reserve1() == bentoBox.balanceOf(token1(), currentContract);
    } else {
        requireInvariant reserveLessThanEqualToBalance();
    }
}