import pytest

from blinkered.cli import parser


def test_closure_arguments():
    args = parser().parse_args(['closure', 'pdr_high', '--via', 'defined_on,uses', '--tag', 'measurement'])
    assert args.node == 'pdr_high'
    assert args.via == ['defined_on', 'uses']
    assert args.tag == ['measurement']


def test_workspace_without_node_resyncs():
    args = parser().parse_args(['workspace'])
    assert args.node is None and not args.all


def test_unknown_command_rejected():
    with pytest.raises(SystemExit):
        parser().parse_args(['graph', 'x'])
