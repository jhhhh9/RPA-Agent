import unittest

from local_rpa_agent.runner import execute_run, preview_data_pipeline


class FakeClient:
    def __init__(self):
        self.statuses = []

    def update_run_status(self, token, run_id, status, success_rows=0, failed_rows=0, error_message=''):
        self.statuses.append({
            'status': status,
            'success_rows': success_rows,
            'failed_rows': failed_rows,
            'error_message': error_message,
        })

    def run(self, token, run_id):
        return {'status': 'running'}


class RunnerTest(unittest.TestCase):
    def test_execute_run_rejects_missing_capability_before_actions(self):
        client = FakeClient()
        run = {
            'id': 'run-1',
            'workflow_snapshot': {
                'entry_node': 'n1',
                'required_capabilities': ['future_action@9'],
                'nodes': [{'node_id': 'n1', 'type': 'log', 'params': {'message': 'ok'}}],
            },
        }

        execute_run(client, 'token', run)

        self.assertEqual(client.statuses[-1]['status'], 'failed')
        self.assertIn('缺少工作流能力', client.statuses[-1]['error_message'])

    def test_preview_data_pipeline_returns_sample_rows(self):
        definition = {
            'entry_node': 'n1',
            'nodes': [{'node_id': 'n1', 'type': 'log'}],
            'data_pipeline': [
                {'step_id': 'set_name', 'type': 'set_field', 'params': {'source': 'rows', 'field': 'name', 'value': 'demo', 'output': 'rows'}},
            ],
        }
        result = preview_data_pipeline(definition, {'rows': [{'id': 1}]})
        self.assertTrue(result['ok'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['sample'][0]['name'], 'demo')


if __name__ == '__main__':
    unittest.main()
