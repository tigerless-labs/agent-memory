---
created: 2026-09-03T01:28:46.685802454Z
updated: 2026-09-03T01:28:46.685802454Z
weight: 1.0
last_accessed: 2026-09-03T01:28:46.685802454Z
access_count: 0
pinned: false
links: []
abstract: May 23, 2023 — ERC-721 music NFT contract for albums and songs; functions analyzed for standard vs custom; merkle proofs, royalties, pricing, artist wallet management; user demonstrated understanding of ERC-721 standards and caught assistant error about tokenURI
---

## Contract Overview
Music-based ERC-721 NFT contract allowing purchase and claiming of albums and individual songs.

## Custom Functions
- `buyAlbum(bytes32[])` — purchase album NFT
- `buySong(bytes32[])` — purchase individual song NFT
- `publicMint()` — public minting of tokens
- `destroyPublic(uint256,uint256)` — destroy/burn tokens
- `claimAlbum(uint256,uint256)` — claim ownership of album
- `setImportantURIs(string,string)` — set base URI, image URL, contract URI
- `reclaimERC20Token(address)` — recover ERC-20 tokens sent to contract
- `reclaimERC721(address,uint256)` — recover ERC-721 tokens sent to contract
- `setStartTimes(uint256,uint256,uint256,uint256)` — set sale start times for albums, songs, public minting, destroy experience
- `setMerkleRoot(bytes32,bytes32)` — set merkle roots for two proof types
- `setArtistWallet(address)` — set artist payment wallet
- `setNFTContract(address)` — set reference to another NFT contract
- `setRoyalty(address,uint96)` — configure royalty distribution
- `setQuorum(uint256)` — set voting quorum for destroy experience
- `setPricePerToken(uint256,uint256)` — set album and song prices
- `setSplitsWallet(address)` — set wallet for split payments
- `withdrawToSplits()` — withdraw funds to splits wallet
- `_isContract(address)` — internal helper to check if address is contract
- `_startTokenId()` — internal to get starting token ID
- `isProofValid(address,uint256,bytes32[])` — merkle proof validation
- `isProofValid2(address,uint256,bytes32[])` — alternative merkle proof validation

## State Variables
- `baseURI`, `imageURL`, `contractURI` — metadata URIs
- `root`, `root2` — merkle roots for two proof types
- `albumSaleStartTime`, `songSaleStartTime`, `publicStartTime`, `destroyExperienceStartTime` — timing controls
- `albumPrice`, `songPrice` — token prices
- `belongsToAlbum` (mapping) — track which tokens are albums
- `MAX_SUPPLY` (constant) — total supply cap
- `quorum` — votes needed for destroy voting
- `songCounter` — track song tokens
- `tokenTypesMap` (mapping) — token type classification
- `destroyExperienceVotes` (mapping) — voting mechanism for token destruction
- `isRestricted` (mapping) — access control per token
- `splitsWallet` — payment split destination
- `nftContract` — reference to IERC721 contract
- `artistWallet` — primary artist payment address

## Note on Standards
User demonstrated knowledge of ERC-721 standards and correctly identified that `tokenURI` is actually part of the ERC-721 Metadata Extension (IERC721Metadata), not a purely custom function. Assistant initially mischaracterized it as custom.