# Threat model

## Protected decision

The checker decides whether the declaration and plan supplied to it imply exact single coverage of the authorized target mask under the declared affine permutation.

## Untrusted components

- certificate producer;
- certificate storage and transport;
- operator-supplied certificate filename;
- every certificate and witness field before recomputation;
- ordering, completeness, and summaries claimed by a transcript.

An adversary may edit values, insert/delete/duplicate/reorder rows, truncate a file, add unknown fields, exploit JSON duplicate keys, substitute a declaration or plan, or provide a nonminimal witness.

## Trusted computing base

- the declaration and plan bytes selected for approval;
- the checker source and Python integer/runtime behavior;
- local file reads and SHA-256 implementation;
- the host executing the checker.

The artifact does not authenticate who selected the inputs. A deployment requiring identity, authorization, freshness, or nonrepudiation must add signatures or another authenticated envelope.

## Defenses

- exact schemas and duplicate-key rejection;
- rejection of booleans in integer fields;
- canonical interval and fragment order;
- canonical SHA-256 binding of declaration and plan;
- fixed expected row count and order;
- per-row sequence and predecessor hash;
- complete arithmetic recomputation;
- canonical witness recomputation;
- arbitrary-precision intermediate integers.

## Explicitly out of scope

- worker compliance or remote execution attestation;
- exactly-once side effects and crash recovery;
- confidentiality or pseudorandomness of the affine map;
- malicious checker host or compromised Python runtime;
- arbitrary PRPs, data-dependent predicates, or multiple independent permutation keys;
- cryptographic signatures, timestamps, transparency logs, or revocation;
- denial of service from inputs accepted outside the published size policy.
