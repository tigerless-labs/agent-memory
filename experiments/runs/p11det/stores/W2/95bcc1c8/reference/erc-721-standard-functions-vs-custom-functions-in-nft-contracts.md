---
name: erc-721-standard-functions-vs-custom-functions-in-nft-contracts
abstract: ERC-721 standard functions vs custom functions in NFT contracts
type: reference
status: active
created: 2026-09-02
updated: 2026-09-02
valid_from: 2026-09-02
superseded_by: null
weight: 1.0
author: cli
links: []
provenance: []
---

ERC-721 Required Functions: name, symbol, totalSupply, balanceOf, ownerOf, approve, getApproved, setApprovalForAll, isApprovedForAll, transferFrom. Optional: mint, burn, metadata, enumerable. Key Correction: tokenURI is NOT part of ERC-721 standard—it is a custom function implementers add to retrieve token URIs. Common custom additions for NFT contracts: purchase mechanics (buyAlbum, buySong), token destruction, merkle proof access control, royalty management, price/time configuration, fund withdrawal, and metadata retrieval.
