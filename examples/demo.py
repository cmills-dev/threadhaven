"""Run after installing Threadhaven. All state lives in an isolated temporary directory."""
import copy
from pathlib import Path
import tempfile
from threadhaven import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='threadhaven-demo-') as temporary:
        root = Path(temporary).resolve()
        repo, store = root / 'project', root / 'private-state'
        repo.mkdir()
        (repo / 'result.txt').write_text('parser implementation v1', encoding='utf-8')
        state = snapshot.template()
        state.update(goal='Finish the parser', progress=['Parser implemented.'],
                     decisions=['Keep the CLI.'], constraints=['Preserve output fields.'],
                     open=['Test malformed input.'], next_action='Run the malformed-input test.',
                     evidence=[{'kind': 'file', 'ref': 'result.txt', 'claim': 'Current implementation'}],
                     external_actions=[{'description': 'Publish release', 'status': 'unknown', 'receipt': ''}])
        first = snapshot.save(store, 'demo', 'parser', 'codex', 'demo-codex', repo, 'none', state)
        folder = snapshot.location(store, 'demo', 'parser')
        received = snapshot.read_record(folder)
        resumed = copy.deepcopy(received['state'])
        resumed['progress'].append('Malformed input checked.')
        resumed['open'] = []
        resumed['next_action'] = 'Review the release draft.'
        second = snapshot.save(store, 'demo', 'parser', 'claude', 'demo-claude', repo, first['id'], resumed)
        print('Codex snapshot read and continued by Claude:', second['id'])
        try:
            snapshot.save(store, 'demo', 'parser', 'codex', 'demo-codex', repo, first['id'], state)
        except snapshot.SnapshotError:
            print('Stale save rejected. Current head preserved.')
        (repo / 'result.txt').write_text('later implementation', encoding='utf-8')
        current = snapshot.read_record(folder)
        print('\n'.join(snapshot.evidence_status(current, repo)))
        assert snapshot.head(folder)['id'] == second['id']
        assert 'CHANGED: result.txt' in snapshot.evidence_status(current, repo)
        assert current['state']['external_actions'][0]['status'] == 'unknown'
        print('Unknown publish outcome retained for destination verification.')
    print('Demo complete. Temporary state removed.')


if __name__ == '__main__':
    main()
