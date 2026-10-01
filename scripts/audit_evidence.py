"""Read-only evidence-chain audit for Tables II and III and the protocol counts."""
from __future__ import annotations

import argparse
import json
from math import gcd
from pathlib import Path

from common import ROOT, bounded


def load(path):
    return json.loads((ROOT / path).read_text())


def exclusive_write(path: Path | None, text: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(text)


def main() -> int:
    bounded()
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-out', type=Path)
    parser.add_argument('--md-out', type=Path)
    args = parser.parse_args()

    cases = load('cases/validation.json')
    validation = load('results/validation.json')
    per_case = load('results/validation-cases.json')
    feistel = load('results/feistel-cases.json')
    boundary = load('results/boundary.json')
    boundary_case = load('cases/boundary.json')
    failure = load('results/resource-failure.json')
    accounting = load('results/resource-accounting.json')

    # Construction accounting: all candidate triples (N,a,b) for N=1..8,
    # followed by the bijection precondition gcd(a,N)=1.
    tiny_candidate_triples = sum(n * n for n in range(1, 9))
    tiny_retained = sum(
        1 for n in range(1, 9) for a in range(n) for _b in range(n)
        if gcd(a, n) == 1
    )
    tiny_excluded_nonbijective = tiny_candidate_triples - tiny_retained

    assert len(cases) == validation['affine_case_records'] == 303
    assert len(per_case) == 303
    assert validation['counts']['plan_oracles'] == 303
    assert validation['counts']['prefix_oracles'] == 3 * 303 == 909
    unsafe = sum(not row['safe'] for row in per_case)
    assert unsafe == validation['unsafe'] == validation['counts']['witness_checks'] == 146
    assert sum(row['safe'] for row in per_case) == validation['safe'] == 157

    mutation_eligible = sum(row['calls'] > 0 for row in per_case)
    mutation_skipped = sum(row['calls'] == 0 for row in per_case)
    floor_record_mutations = 2 * mutation_eligible
    truncation_checks = len(per_case)
    trailing_checks = len(per_case)
    actual_corruption_comparisons = (
        floor_record_mutations + truncation_checks + trailing_checks
    )
    assert mutation_eligible == 294 and mutation_skipped == 9
    assert actual_corruption_comparisons == validation['counts']['certificate_mutations'] == 1194

    assert len(feistel) == validation['counts']['feistel_functions'] == 276
    assert validation['counts']['feistel_point_checks'] == 16656

    declaration = boundary_case['declaration']
    plan = boundary_case['plan']
    assert declaration['n'] == 1 << 32
    assert len(declaration['history']) == 61
    assert len(plan['future']) == 64
    assert len(declaration['epochs'][0]['exclude']) == 1024
    rows = declaration['history'] + plan['future']
    assert len(rows) == 125
    assert all(len(row['guard']) == 1024 for row in rows)

    certificate = ROOT / 'results' / 'boundary-certificate.jsonl'
    certificate_bytes = certificate.stat().st_size
    total_lines = 0
    floor_records = 0
    with certificate.open(encoding='utf-8') as stream:
        for position, line in enumerate(stream):
            total_lines += 1
            record = json.loads(line)
            if position == 0:
                assert record == {'prefix': 1 << 32}
            elif isinstance(record, list):
                assert len(record) == 2 and isinstance(record[1], list)
                floor_records += 1
            else:
                assert set(record) == {'defects', 'accepted'}
    assert total_lines == floor_records + 2
    assert certificate_bytes == boundary['symbolic']['certificate_bytes'] == 32816640
    assert floor_records == boundary['symbolic']['floor_calls'] == 514048
    assert boundary['symbolic']['rows'] == 125
    assert boundary['symbolic']['old_shards'] == 61
    assert boundary['symbolic']['new_shards'] == 64
    assert boundary['symbolic']['exclusions'] == 1024
    assert boundary['symbolic']['guard_intervals'] == 1024
    assert boundary['exact']['n'] == 1 << 20

    counts = validation['counts']
    table_ii_sum = sum(counts[key] for key in (
        'floor_oracles', 'crt_oracles', 'plan_oracles', 'prefix_oracles',
        'witness_checks', 'certificate_mutations', 'schema_mutations',
        'feistel_functions',
    ))
    assert table_ii_sum == validation['obligation_count'] == 23676

    report = {
        'project_key': 'mask-aware-certificates-for-permutation-complete-stateless-scan-plans',
        'audit_kind': 'read_only_mapping_of_retained_evidence',
        'table_ii': {
            'floor_tuple_comparisons': counts['floor_oracles'],
            'crt_intersection_comparisons': counts['crt_oracles'],
            'affine_plan_records_compared': counts['plan_oracles'],
            'prefix_comparisons_actual': counts['prefix_oracles'],
            'least_witness_comparisons_actual': counts['witness_checks'],
            'certificate_corruptions_actual': counts['certificate_mutations'],
            'malformed_input_comparisons_actual': counts['schema_mutations'],
            'feistel_constructions_actual': counts['feistel_functions'],
            'sum': table_ii_sum,
            'feistel_point_checks_reported_separately': counts['feistel_point_checks'],
        },
        'selection_and_skip_accounting': {
            'tiny_candidate_parameter_triples': tiny_candidate_triples,
            'tiny_retained_bijective_triples': tiny_retained,
            'tiny_excluded_by_declared_gcd_precondition': tiny_excluded_nonbijective,
            'arbitrary_mask_attempted': 96,
            'arbitrary_mask_retained': 96,
            'guarded_controls_attempted': 3,
            'guarded_controls_retained': 3,
            'multi_epoch_attempted': 1,
            'multi_epoch_retained': 1,
            'remove_or_duplicate_variants_attempted': 80,
            'remove_or_duplicate_variants_retained': 80,
            'validation_records_actual': len(cases),
            'floor_record_mutation_eligible_certificates': mutation_eligible,
            'floor_record_mutation_inapplicable_certificates': mutation_skipped,
            'floor_record_mutation_comparisons_actual': floor_record_mutations,
            'truncation_comparisons_actual': truncation_checks,
            'trailing_record_comparisons_actual': trailing_checks,
            'certificate_corruptions_actual': actual_corruption_comparisons,
        },
        'table_iii': {
            'domain': boundary['symbolic']['n'],
            'history_fragments': len(declaration['history']),
            'future_fragments': len(plan['future']),
            'total_fragments': len(rows),
            'exclusion_intervals': len(declaration['epochs'][0]['exclude']),
            'guard_intervals_per_fragment': min(len(row['guard']) for row in rows),
            'certificate_bytes': certificate_bytes,
            'certificate_mib': certificate_bytes / (1024 * 1024),
            'certificate_total_lines': total_lines,
            'floor_query_records': floor_records,
            'euclidean_triples_checked': boundary['symbolic']['euclidean_steps'],
            'recorded_producer_cpu_seconds': boundary['symbolic']['producer_cpu_seconds'],
            'recorded_checker_cpu_seconds': boundary['symbolic']['checker_cpu_seconds'],
            'recorded_combined_peak_rss_kib': boundary['peak_rss_kib'],
            'recorded_combined_peak_rss_mib': boundary['peak_rss_kib'] / 1024,
            'recorded_whole_boundary_cpu_seconds': boundary['cpu_seconds'],
            'separate_exact_oracle_domain': boundary['exact']['n'],
            'recorded_counter_oracle_cpu_seconds': boundary['exact']['enumeration_cpu_seconds'],
            'recorded_replay_oracle_cpu_seconds': boundary['exact']['replay_cpu_seconds'],
        },
        'failed_run_and_repair': {
            'outcome': failure['outcome'],
            'actual_failed_run_cpu_seconds': failure['recorded_cpu_seconds'],
            'budget_charge_seconds_not_measurement': failure['cpu_budget_charge_seconds'],
            'retained_observation': failure['retained_observation'],
            'repair': failure['repair'],
            'complete_campaign_cpu_measurement': accounting['complete_cumulative_cpu_measurement'],
        },
        'source_map': {
            '303_inputs': 'cases/validation.json',
            '303_per_case_results': 'results/validation-cases.json',
            'aggregate_counts': 'results/validation.json',
            '276_feistel_records': 'results/feistel-cases.json',
            'boundary_input': 'cases/boundary.json',
            'boundary_certificate': 'results/boundary-certificate.jsonl',
            'boundary_observation': 'results/boundary.json',
            'failed_run': 'results/resource-failure.json',
            'resource_accounting': 'results/resource-accounting.json',
        },
        'all_checks_passed': True,
    }

    md = f"""# Evidence map for Tables II and III

This is a read-only audit of retained files. It does not relabel a new run as
the original observation.

## Table II

- 303 retained affine plans map to `cases/validation.json` and 303 rows in
  `results/validation-cases.json`.
- The 909 prefix comparisons are exactly three actual comparisons for each
  retained plan.
- The 146 witness checks equal the 146 unsafe retained plans.
- The 1,194 corruption checks are actual verifier calls: 588 record-level
  mutations on 294 certificates that contain floor records, plus 303
  truncations and 303 trailing-record checks. Nine shortcut-only certificates
  contain no floor record, so the two record-level mutation types are
  inapplicable rather than silently counted.
- The 123 tiny plans come from 204 candidate `(N,a,b)` triples for `1 <= N <=
  8`; 81 are excluded by the declared `gcd(a,N)=1` precondition. The 96
  arbitrary-mask plans, 3 guard controls, 1 multi-epoch plan and 80 functional
  variants were all retained.
- 276 Feistel truth tables were constructed and compared; 16,656 point checks
  are reported separately rather than added to the 23,676 named obligations.

## Table III

- Input: 61 declared-history residue fragments, 64 future residue fragments,
  1,024 exclusions and 1,024 guard intervals per fragment over `N=2^32`.
- Certificate: {certificate_bytes:,} bytes ({certificate_bytes / 1048576:.3f}
  MiB), {floor_records:,} floor-query records and
  {boundary['symbolic']['euclidean_steps']:,} checked Euclidean triples.
- Frozen observation: producer {boundary['symbolic']['producer_cpu_seconds']:.3f}
  CPU s, checker {boundary['symbolic']['checker_cpu_seconds']:.3f} CPU s,
  combined-run peak {boundary['peak_rss_kib'] / 1024:.3f} MiB. These are the
  retained single-run observations, not values from this audit.
- The failed first run has no measured CPU duration. The 115 s value is an
  explicit budget charge, not an observation. Its repair is the empty-lattice
  short-circuit recorded in `results/resource-failure.json`.

## Exact source map

See `results/evidence-map.json` for machine-readable fields and exact paths.
"""

    json_text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    exclusive_write(args.json_out, json_text)
    exclusive_write(args.md_out, md)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
