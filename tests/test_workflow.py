from local_rpa_agent.workflow import WorkflowExecutor, render_template


def test_render_template_row_value():
    assert render_template("hello {{row.name}}", {"name": "Temu"}) == "hello Temu"


def test_executor_runs_linear_workflow():
    definition = {
        "entry_node": "n1",
        "nodes": [
            {"node_id": "n1", "type": "log", "params": {"message": "start {{row.id}}"}, "next": "n2"},
            {"node_id": "n2", "type": "sleep", "params": {"seconds": 0}},
        ],
    }
    result = WorkflowExecutor().execute(definition, row={"id": "AC001"})
    assert result.success_rows == 1
    assert result.failed_rows == 0
    assert result.logs[0].message == "start AC001"
