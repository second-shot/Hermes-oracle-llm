"""Local operator entrypoint: no model downloads or automatic cloud fallback."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOCAL_MODEL_KEY = 'qwen3-1.7b'
LOCAL_MODEL_ALIAS = 'hermes-free'
LARGE_MODEL_KEY = 'qwen3.5-4b-verified'
LOCAL_CONTEXT_LENGTH = '2048'


def freebuff_command(executable=None, project_root=ROOT):
    executable = Path(executable) if executable else shutil.which('freebuff')
    if not executable:
        raise RuntimeError('Freebuff CLI is missing. Install it with: npm install -g freebuff')
    return [str(executable), '--cwd', str(project_root)]


def launch_freebuff(executable=None, project_root=ROOT, run=subprocess.call):
    command = freebuff_command(executable=executable, project_root=project_root)
    return run(command, cwd=str(project_root))


def model_needs_reload(loaded, desired_model_key=LOCAL_MODEL_KEY):
    alias_entry = next((m for m in loaded if m.get('identifier') == LOCAL_MODEL_ALIAS), None)
    if alias_entry is None:
        return True
    identity = ' '.join(
        str(alias_entry.get(key, ''))
        for key in ('modelKey', 'path', 'indexedModelIdentifier')
    ).lower()
    return desired_model_key.lower() not in identity


def prepare_model():
    lms = Path.home() / '.lmstudio/bin/lms.exe'
    if not lms.is_file():
        raise RuntimeError('LM Studio CLI is missing.')
    subprocess.run([str(lms), 'daemon', 'up'], check=True, timeout=180)
    loaded = json.loads(subprocess.check_output([str(lms), 'ps', '--json'], text=True, timeout=30))
    if model_needs_reload(loaded):
        if any(m.get('identifier') == LOCAL_MODEL_ALIAS for m in loaded):
            subprocess.run([str(lms), 'unload', LOCAL_MODEL_ALIAS], check=True, timeout=60)
        subprocess.run([str(lms), 'load', LOCAL_MODEL_KEY, '--context-length', LOCAL_CONTEXT_LENGTH,
                        '--identifier', LOCAL_MODEL_ALIAS, '--gpu', 'off', '--parallel', '1'],
                       check=True, timeout=180)
    subprocess.run([str(lms), 'server', 'start'], check=True, timeout=30)


def _resale_status_next_action(action_result):
    pending = int(action_result.get('pending_approvals') or 0)
    inventory = int(action_result.get('inventory_count') or 0)
    latest_item_id = action_result.get('latest_item_id')
    if pending:
        return f"Review the {pending} pending resale approval before generating more drafts."
    if inventory and latest_item_id:
        return f"Open {latest_item_id} and generate its listing draft for approval."
    if inventory:
        return "Open the newest inventory item and generate its listing draft for approval."
    return "Capture one item with title, condition, and photos."


def execute_operator_task(task, config, *, model_execute=None, resale_service=None):
    from core.executor import execute_task
    from hermes_brain import HermesBrain
    from resale_agents.service import ResaleAgentService

    brain = HermesBrain()
    decision = brain.intake(task)
    action = None
    action_result = None
    next_action = decision.next_step

    status_request = any(token in decision.normalized_request.lower() for token in ('status', 'health', 'inventory count'))
    if decision.specialist == 'RESALE AGENT' and status_request:
        action = 'resale_agents.health'
        action_result = (resale_service or ResaleAgentService()).health()
        next_action = _resale_status_next_action(action_result)

    model_prompt = task
    if action:
        model_prompt = (
            f"User task: {task}\n"
            f"Mia route: {decision.route} -> {decision.specialist}\n"
            f"Local action executed: {action}\n"
            f"Verified action result: {json.dumps(action_result, ensure_ascii=False, sort_keys=True)}\n"
            f"Mia verified next action: {next_action}\n"
            "Briefly state the verified result and repeat that next action. Do not invent external actions."
        )

    inference = (model_execute or execute_task)(model_prompt, config)
    output = {
        'route': decision.route,
        'specialist': decision.specialist,
        'action': action,
        'action_result': action_result,
        'result': inference.get('result') or inference.get('message') or decision.next_step,
        'next_action': next_action,
        'cache': inference.get('cache', 'miss'),
    }
    if inference.get('meta'):
        output['inference'] = inference['meta']
    if inference.get('error'):
        output['error'] = inference['error']

    brain.record_outcome(decision, output)
    return output


def main():
    parser = argparse.ArgumentParser(description='Mia local operator')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--task', help='Run one local model task')
    modes.add_argument('--smoke', action='store_true')
    modes.add_argument('--doctor', action='store_true')
    modes.add_argument('--serve', action='store_true')
    modes.add_argument('--freebuff', action='store_true', help='Open Freebuff on the Mia project')
    modes.add_argument('--employee', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.employee is not None:
        return subprocess.call([sys.executable, str(ROOT / 'hermes_employee.py'), *args.employee])
    if args.freebuff:
        return launch_freebuff()
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    if config.get('cloud_enabled') or config.get('llm', {}).get('provider') != 'local_router':
        raise RuntimeError('Operator requires cloud_enabled=false and llm.provider=local_router.')
    prepare_model()
    if args.doctor or args.serve:
        return subprocess.call([sys.executable, str(ROOT / 'scripts/hermes_doctor.py'),
                                *(['--start'] if args.serve else [])])
    from memory.store import log_session

    def run(task):
        result = execute_operator_task(task, config)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        log_session(task, result)
        return int(bool(result.get('error')) or not bool(result.get('result')))

    if args.smoke:
        from datetime import datetime, timezone
        from resale_agents.service import ResaleAgentService
        from runtime_state import resolve_data_root
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        smoke_root = resolve_data_root() / 'smoke' / stamp
        os.environ['HERMES_DATA_DIR'] = str(smoke_root)
        service = ResaleAgentService()
        captured = service.capture_item({'title': 'SMOKE TEST Seiko watch', 'brand': 'Seiko',
                                        'condition': 'good', 'photos': ['test-front.jpg']})
        draft = service.run_until_approval(captured['data']['item']['item_id'])
        assert draft['data']['approval_required'] is True
        assert ResaleAgentService().health()['inventory_count'] == 1
        print(json.dumps({'resale_draft': 'PASS', 'persisted': True, 'published': False,
                          'smoke_data': str(smoke_root)}, indent=2), flush=True)
        os.environ['HERMES_DATA_DIR'] = str(smoke_root / 'inference')
        return run(f'Give one short tip for photographing a watch. Test {stamp}.')
    if args.task:
        return run(args.task)
    print('Mia local operator. Enter a task; type exit to stop.', flush=True)
    while True:
        try:
            task = input('\nMia> ').strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if task.lower() in {'exit', 'quit'}:
            return 0
        if task:
            run(task)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f'[FAIL] {exc}', file=sys.stderr)
        raise SystemExit(1)
