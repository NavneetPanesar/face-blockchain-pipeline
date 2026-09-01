// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SocialVerifier {

    struct Record {
        string   postUrl;
        uint256  timestamp;
        address  submitter;
        uint16   similarity;   // e.g. 7523 means 75.23 %
    }

    mapping(bytes32 => Record) public records;
    bytes32[] public allHashes;

    event DataStored(
        bytes32 indexed dataHash,
        string          postUrl,
        address indexed submitter,
        uint256         timestamp,
        uint16          similarity
    );

    function store(
        bytes32        dataHash,
        string calldata postUrl,
        uint16          similarity
    ) external {
        require(records[dataHash].timestamp == 0, "Hash already stored");
        records[dataHash] = Record(postUrl, block.timestamp, msg.sender, similarity);
        allHashes.push(dataHash);
        emit DataStored(dataHash, postUrl, msg.sender, block.timestamp, similarity);
    }

    function verify(bytes32 dataHash)
        external
        view
        returns (
            bool    exists,
            string memory postUrl,
            uint256 timestamp,
            address submitter,
            uint16  similarity
        )
    {
        Record memory r = records[dataHash];
        return (r.timestamp != 0, r.postUrl, r.timestamp, r.submitter, r.similarity);
    }

    function count() external view returns (uint256) {
        return allHashes.length;
    }
}
