import unittest

import mock
from nose.tools import eq_

from opennode.oms.endpoint.ssh.protocol import OmsSshProtocol
from opennode.oms.endpoint.ssh import cmd
from opennode.oms.model.model.compute import Compute
from opennode.oms.tests.util import run_in_reactor
from opennode.oms.zodb import db


class CmdCompletionTestCase(unittest.TestCase):

    def setUp(self):
        self.oms_ssh = OmsSshProtocol()
        self.terminal = mock.Mock()
        self.oms_ssh.terminal = self.terminal

        self.oms_ssh.connectionMade()

        # the standard model doesn't have any command or path which
        # is a prefix of another (len > 1), I don't want to force changes
        # to the model just for testing completion, so we have monkey patch
        # the commands() function and add a command 'hello'.
        self.orig_commands = cmd.commands
        cmd.commands = lambda: dict(hello=cmd.Cmd, **self.orig_commands())

    def tearDown(self):
        cmd.commands = self.orig_commands

    def _input(self, string):
        for s in string:
            self.oms_ssh.characterReceived(s, False)

    def _tab_after(self, string):
        self._input(string)
        self.terminal.reset_mock()

        self.oms_ssh.handle_TAB()

    def test_command_completion(self):
        self._tab_after('s')
        eq_(self.terminal.method_calls, [('write', ('et ',), {})])

    def test_command_completion_spaces(self):
        self._tab_after('    s')
        eq_(self.terminal.method_calls, [('write', ('et ',), {})])

    def test_complete_not_found(self):
        self._tab_after('t')
        eq_(len(self.terminal.method_calls), 0)

    def test_complete_quotes(self):
        self._tab_after('ls "comp')
        eq_(self.terminal.method_calls, [('write', ('utes/',), {})])

    def test_complete_prefix(self):
        self._tab_after('h')
        eq_(self.terminal.method_calls, [('write', ('el',), {})])

        # hit tab twice
        self.terminal.reset_mock()
        self.oms_ssh.handle_TAB()

        eq_(self.terminal.method_calls, [('write', ('',), {}), ('nextLine', (), {}), ('write', ('help  hello\n',), {}), ('write', (self.oms_ssh.ps[0] + 'hel',), {})])

    def test_spaces_between_arg(self):
        self._tab_after('ls comp')
        eq_(self.terminal.method_calls, [('write', ('utes/',), {})])

    def test_command_arg_spaces_before_command(self):
        self._tab_after(' ls comp')
        eq_(self.terminal.method_calls, [('write', ('utes/',), {})])

    def test_mandatory_positional(self):
        self._tab_after('cat ')
        eq_(len(self.terminal.method_calls), 4)

    def test_complete_switches(self):
        self._tab_after('quit ')
        eq_(len(self.terminal.method_calls), 0)

        # hit tab twice
        self.oms_ssh.handle_TAB()
        eq_(len(self.terminal.method_calls), 0)

        # now try with a dash
        self._tab_after('-')
        eq_(self.terminal.method_calls, [('write', ('',), {}), ('nextLine', (), {}), ('write', ('-h  --help\n',), {}), ('write', (self.oms_ssh.ps[0] + 'quit -',), {})])
        # disambiguate
        self._tab_after('-')
        eq_(self.terminal.method_calls, [('write', ('help ',), {})])

    def test_complete_consumed_switches(self):
        self._tab_after('ls --help')
        eq_(self.terminal.method_calls, [('write', (' ',), {})])

        self._tab_after('-')
        assert 'help' not in self.terminal.method_calls[2][1][0]
        assert '-h' not in self.terminal.method_calls[2][1][0]

    @run_in_reactor
    def test_complete_contextualized_no_context(self):
        self._tab_after('set /comp')
        eq_(self.terminal.method_calls, [('write', ('utes/',), {})])

    @run_in_reactor
    def test_complete_keyword_switches(self):
        computes = db.get_root()['oms_root']['computes']
        computes.add(Compute('linux', 'tux-for-test', 2000, 2000, 'active'))

        self._tab_after('set /computes/1 arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

    @run_in_reactor
    def test_complete_keyword_switches_mk(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

    @run_in_reactor
    def test_complete_consumed_keyword_switches_mk(self):
        """Test consuming of already completed switches when there are mandatory arguments."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk compute arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

        self._tab_after('li')
        eq_(self.terminal.method_calls, [('write', ('nux ',), {})])

        self._tab_after('arch')
        eq_(self.terminal.method_calls, [])

    @run_in_reactor
    def test_complete_mk_legal_types(self):
        """Test that only legal types are shown."""
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk net')
        eq_(self.terminal.method_calls, [])

        self.oms_ssh.handle_RETURN()
        self.terminal.reset_mock()

        self._tab_after('mk comp')
        eq_(self.terminal.method_calls, [('write', ('ute ',), {})])

        self._tab_after('arch')
        eq_(self.terminal.method_calls, [('write', ('itecture=',), {})])

    @run_in_reactor
    def test_complete_positional_choice(self):
        self.oms_ssh.lineReceived('cd computes')

        self._tab_after('mk comp')
        eq_(self.terminal.method_calls, [('write', ('ute ',), {})])

        self._tab_after('comp')
        eq_(self.terminal.method_calls, [])
