# Safe-anchor update protocol

The underlying declaration, fragment, mask and epoch semantics are unchanged.
Forbidden multiplicity has a linear penalty. An update changes future
occurrences and, optionally, epoch policies. It does not change the affine
context, epoch count/order or trusted historical list.

A `SafeAnchor` can be established only by full safe verification of immutable
snapshots of old declaration/plan inputs. A parsed but unsafe certificate or a
certificate for prefix zero is not an anchor. The Python object is a trusted
in-process capability, not authentication against arbitrary code in that
process, a signature, or a serialized checkpoint. No externally supplied
self-hash establishes this premise. The object retains O(input bytes) state.

Producer matching uses a hash queue; checker matching uses a sorted merge of
complete row values. Equal occurrences are paired in increasing position
order. The header is exactly `{kind, prefix, removed, added}`; `kind` must be
`safe-anchor-update`; position lists must match the actual multiset difference.
Order is epochs, changed-policy symmetric-difference queries, removed singles,
added singles, added/added pairs, added/removed pairs, then a trailer containing
`defects` and `accepted`. Each nontrivial interval uses the original floor
transcript format and bounds. Guard and policy intersections are reconstructed
by the checker. Prefix is a source counter bound, never target order.

`advance_anchor` accepts only a safe full update and takes immutable snapshots
before checking. A failed update never supplies a premise for another update.
Changing history/context or restarting without trustworthy state requires full
re-establishment. Input validation and exact occurrence matching still inspect
unchanged input; only the counting work loses that background dependence.

## Cold commands (all paths relative to the artifact root)

Each invocation below rechecks the base, so its runtime is **cold**:

```sh
python pcs-update.py check examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/safe-plan.json examples/updates/safe-update.jsonl
python pcs-update.py check examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/unsafe-plan.json examples/updates/unsafe-update.jsonl
python pcs-update.py check-witness examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/unsafe-plan.json examples/updates/witness
```

Expected exit codes are respectively 0, 1, 0. A truncated transcript returns 2.
Use `certify ... --out NEW_FILE` to generate a transcript, and `diagnose ...
NEW_DIRECTORY` to generate a three-certificate witness bundle. Existing outputs
are rejected rather than overwritten. Generation exit 0 is not an independent
safe check. The witness here is a single missing counter 2/target17; the older
full-check diagnostic is a distinct plan with D(50)=12.

## Warm API

Run from the repository root, explicitly putting `src` first. Merely setting
PYTHONPATH while running in the root can select the root `pcs.py` CLI instead
of the package on some Python invocation forms.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
from pcs.model import load, certificate_lines
from pcs.update_checker import establish_anchor, verify_update, advance_anchor
p = Path('examples/updates')
spec = load(p / 'declaration.json')
old = load(p / 'old-plan.json')
anchor = establish_anchor(spec, old, certificate_lines(p / 'old-certificate.jsonl'))
new = load(p / 'safe-plan.json')
result = verify_update(anchor, spec, new, certificate_lines(p / 'safe-update.jsonl'))
assert result.accepted and result.defects == (0,)
# This fully checks once more before advancing; verify_update itself is read-only.
anchor = advance_anchor(anchor, spec, new, certificate_lines(p / 'safe-update.jsonl'))
```

Public CLI calls and the import path are executed by
`scripts/test_update_contract.py`. Static and runtime import checks exclude
producer/oracle imports from both checker modules. The update checker shares
only the existing checker arithmetic, parser/schema/limits and Python runtime.
The Boolean and SMT frontends are separate optional consumers of the invariant;
neither is a dependency of transcript verification.
