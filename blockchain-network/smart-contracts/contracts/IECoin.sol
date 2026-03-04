// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract IECoin is ERC20, Ownable {
    constructor(uint256 initialSupply, address initialOwner)
        ERC20("IECoin", "IEC")
        Ownable(initialOwner)
    {
        _mint(initialOwner, initialSupply);
    }
}