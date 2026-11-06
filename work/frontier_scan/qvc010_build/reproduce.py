"""Reproduce the scored public portfolio and run unmodified official verifiers.

Copyright 2026 daifanhao. Licensed under Apache-2.0 for this orchestration code.
Upstream circuit artifacts and source retain their original terms; see CREDITS.md.
"""
import argparse
import hashlib
import json
import lzma
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def unpack(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as packed:
        for info in packed.infolist():
            if not (target / info.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError('Unsafe archive member')
        packed.extractall(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--competition', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data, competition, output = args.data.resolve(), args.competition.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    release = json.loads((data / 'RELEASE.json').read_text())
    for name, record in release['files'].items():
        if digest(data / name) != record['sha256']:
            raise ValueError(f'Input differs from pinned release: {name}')
    print('Pinned release:', release['release_id'], flush=True)
    upstream = output / 'upstream'
    unpack(data / 'public_release.bundle', upstream)
    manifest = json.loads((upstream / 'QCC_RELEASE_MANIFEST.json').read_text())
    if manifest['portfolio'] != 'v76_y33_ay3':
        raise ValueError('Unexpected upstream portfolio')
    submission = output / 'submission'
    submission.mkdir(exist_ok=False)
    for item in manifest['files']:
        source, target = upstream / item['stored_as'], submission / item['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == '.xz':
            with lzma.open(source, 'rb') as inp, target.open('wb') as out:
                shutil.copyfileobj(inp, out, 4 << 20)
        else:
            shutil.copy2(source, target)
        if digest(target) != item['sha256']:
            raise ValueError(f'Upstream artifact mismatch: {item["file"]}')
    print('Assembled the complete public C44 family and baseline decoder.', flush=True)

    # Exact scanner/emitter by Atakan Aldemir, preserved without source changes.
    # Run the scanner on this exact binary; offsets from another circuit are invalid.
    scan = output / 'chain_scan'
    command = [sys.executable, str(data / 'dqi_chain_cache_v4.py'),
               '--input', str(submission / 'dqi.kmb'), '--out', str(scan),
               '--words', '512', '--collision-bits', '64', '--num-inputs', '840']
    with (output / 'scanner.log').open('w') as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    plan = json.loads((scan / 'report.json').read_text())
    print('Exact scanner:', {k: plan[k] for k in ('selected_chains', 'replaced_gates', 'static_savings')}, flush=True)
    sys.path.insert(0, str(data))
    from dqi_chain_cache_emit_v4 import emit
    plan['_folder'] = str(scan)
    candidate = output / 'dqi_rewritten.kmb'
    emission = emit(submission / 'dqi.kmb', plan, candidate)
    write_json(output / 'emission.json', emission)
    candidate.replace(submission / 'dqi.kmb')
    expected = json.loads((data / 'expected_artifacts.json').read_text())
    actual_names = {str(p.relative_to(submission)) for p in submission.rglob('*') if p.is_file()}
    if actual_names != set(expected):
        raise ValueError('Submission must contain exactly the scored 18 files')
    for name, record in expected.items():
        if digest(submission / name) != record['sha256']:
            raise ValueError(f'Rebuilt artifact differs from the scored version: {name}')
    print('Rebuilt all 18 scored artifacts, including DQI:', emission, flush=True)

    # Official CLI entry points, full default shot counts and the empty default salt.
    # The reference Hamiltonian and runtime come only from attached competition data.
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(competition / 'kickmix'),
        str(competition / 'verifiers'), env.get('PYTHONPATH', '')])
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        env[name] = '4'
    reports = {}
    shots = {'dfthcsos': 78080, 'invsqrt': 200540928, 'dqi': 102400}
    for task in ('dfthcsos', 'invsqrt', 'dqi'):
        script = competition / 'verifiers' / task / ('verify.py' if task == 'dfthcsos' else f'verify_submission_{task}.py')
        target = submission / (task if task == 'dfthcsos' else task + '.kmb')
        command = [sys.executable, str(script), str(target), '--salt', '']
        if task != 'dfthcsos':
            command += ['--max-workers', '4']
        started = time.monotonic()
        print(f'{task}: official full verification, {shots[task]:,} shots', flush=True)
        with (output / f'official_{task}.json').open('w') as log, (output / f'official_{task}.stderr').open('w') as err:
            subprocess.run(command, check=True, stdout=log, stderr=err, env=env, timeout=1200)
        report = json.loads((output / f'official_{task}.json').read_text())
        if report['status'] != 'PASS' or report['verified_shots'] != shots[task]:
            raise ValueError(f'Incomplete official verification: {task}')
        key = 'submission_sha256' if task == 'dfthcsos' else 'circuit_sha256'
        if report[key] != release['official_artifact_digests'][task]:
            raise ValueError(f'Official report artifact differs: {task}')
        reports[task] = report
        print(task, 'PASS', 'cost', report['score'], 'seconds', round(time.monotonic() - started, 2), flush=True)
    local_score = math.exp(sum(math.log(release['reference_costs'][task] / report['score'])
                              for task, report in reports.items()) / 3)
    summary = {'status': 'PASS', 'local_aggregate': local_score,
               'reported_public_score': release['public_score'],
               'reported_submission_ref': release['submission_ref'],
               'salt': '', 'task_costs': {t: r['score'] for t, r in reports.items()},
               'emission': emission}
    write_json(output / 'reproduction_summary.json', summary)
    # Preserve the exact accepted ZIP container. Its payload hashes were checked
    # when this release was made; the freshly rebuilt payload matches every entry.
    shutil.copy2(data / 'scored_submission.bundle', output / 'submission.zip')
    for name in ('CREDITS.md', 'LICENSE.md', 'UPSTREAM_HELIOS_CREDITS.md',
                 'UPSTREAM_HELIOS_LICENSE.md', 'APACHE-2.0.txt', 'SOURCE_PROVENANCE.json'):
        shutil.copy2(data / name, output / name)
    print(json.dumps(summary, indent=2), flush=True)
    print('Ready:', output / 'submission.zip', 'SHA256', digest(output / 'submission.zip'), flush=True)


if __name__ == '__main__':
    main()
