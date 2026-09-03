---
name: building-erc-721-nft-contract-for-music-with-album-and-song-purchases
abstract: Building ERC-721 NFT contract for music with album and song purchases
type: fact
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2023-05-23
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

# Music NFT (ERC-721) Smart Contract

## Contract Purpose
Custom ERC-721 contract extending standard NFT to support buying/claiming music albums and songs, with royalties, merkle-tree whitelisting, and phased public/restricted minting.

## Key Custom Functions
- buyAlbum(), buySong() — purchase tokens
- publicMint(), claimAlbum() — mint tokens
- destroyPublic() — burn tokens with voting
- setMerkleRoot(), setArtistWallet(), setRoyalty(), setPricePerToken(), setStartTimes() — configuration
- withdrawToSplits(), reclaimERC20Token(), reclaimERC721() — fund management
- isProofValid(), isProofValid2() — merkle proof verification

## Key State Variables
- albumPrice, songPrice, quorum (pricing & governance)
- ablumSaleStartTime, songSaleStartTime, publicStartTime, destroyExperienceStartTime (phased timing)
- baseURI, imageURL, contractURI, root, root2 (metadata & merkle trees)
- splitsWallet, nftContract, artistWallet (external references)
- tokenTypesMap, belongsToAlbum, isRestricted, destoryExperinceVotes (tracking mappings)
- songCounter, MAX_SUPPLY (supply management)

## Standard ERC-721 Functions Implemented
name, symbol, balanceOf, ownerOf, approve, getApproved, setApprovalForAll, isApprovedForAll, transferFrom, supportsInterface, tokenURI, _startTokenId

## Design Notes
- Dual merkle root system for multi-phase whitelist verification
- ERC-2981 royalty standard integration
- Split wallet pattern for multi-recipient payouts
- Governance via quorum and voting on token destruction
