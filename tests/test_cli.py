import pytest

from blinkered.cli import parser


def test_closure_arguments():
    args = parser().parse_args(['closure', 'selection', '--via', 'reads,uses', '--tag', 'transform'])
    assert args.node == 'selection'
    assert args.via == ['reads', 'uses']
    assert args.tag == ['transform']


def test_workspace_without_node_resyncs():
    args = parser().parse_args(['workspace'])
    assert args.node is None and not args.all


def test_unknown_command_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(['graph', 'x'])
