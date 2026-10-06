#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, platform, time, urllib.error, urllib.request

class PocketAIComputerAgent:
    def __init__(self, phone: str, token: str, interval: float = 1.0) -> None:
        self.phone, self.token, self.interval = phone.rstrip('/'), token, max(0.2, interval)
        self.agent_name = platform.node() or 'computer'

    def request(self, method, path, payload=None, timeout=8.0):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'}
        if data is not None: headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.phone + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=timeout)

    def hello(self):
        try:
            with self.request('GET', '/v1/agent/hello') as r: return r.status == 200
        except (urllib.error.URLError, TimeoutError, OSError): return False

    def poll(self):
        try:
            with self.request('GET', '/v1/agent/tasks/next', timeout=30) as r:
                if r.status == 204: return None
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

    def execute(self, task):
        action = str(task.get('action', '')).strip()
        args = task.get('args') or {}
        if action == 'ping':
            return {'id': str(task.get('id', 'unknown')), 'ok': True, 'action': 'ping',
                    'computer': self.agent_name, 'platform': platform.platform(),
                    'message': str(args.get('message', 'pong'))}
        return {'id': str(task.get('id', 'unknown')), 'ok': False, 'action': action,
                'error': 'action not enabled in LAN MVP'}

    def report(self, result):
        try:
            with self.request('POST', '/v1/agent/tasks/result', result, timeout=8) as r: r.read()
        except (urllib.error.URLError, TimeoutError, OSError): pass

    def run(self):
        print('PocketAI Computer Agent: ' + self.agent_name)
        print('Phone: ' + self.phone)
        connected = False
        while True:
            now = self.hello()
            if now != connected:
                connected = now
                print('Connected to PocketAI phone.' if connected else 'Phone connection lost.')
            if connected:
                task = self.poll()
                if task:
                    print('Task:', task.get('id'), 'action=', task.get('action'))
                    result = self.execute(task)
                    self.report(result)
                    print('Result:', json.dumps(result, ensure_ascii=False))
            time.sleep(self.interval)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phone', required=True)
    p.add_argument('--token', required=True)
    p.add_argument('--interval', type=float, default=1.0)
    a = p.parse_args()
    PocketAIComputerAgent(a.phone, a.token, a.interval).run()

if __name__ == '__main__': main()
