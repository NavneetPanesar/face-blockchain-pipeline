// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SocialVerifier {
    struct Record {
        string postUrl;
        uint256 timestamp;
        address submitter;
    }

    mapping(bytes32 => Record) public records;
    bytes32[] public allHashes;

    event DataStored(
        bytes32 indexed dataHash,
        string postUrl,
        address indexed submitter,
        uint256 timestamp
    );

    function store(bytes32 dataHash, string calldata postUrl) external {
        require(records[dataHash].timestamp == 0, "Hash already stored");
        records[dataHash] = Record(postUrl, block.timestamp, msg.sender);
        allHashes.push(dataHash);
        emit DataStored(dataHash, postUrl, msg.sender, block.timestamp);
    }

    function verify(bytes32 dataHash)
        external
        view
        returns (
            bool exists,
            string memory postUrl,
            uint256 timestamp,
            address submitter
        )
    {
        Record memory r = records[dataHash];
        return (r.timestamp != 0, r.postUrl, r.timestamp, r.submitter);
    }

    function count() external view returns (uint256) {
        return allHashes.length;
    }
}
