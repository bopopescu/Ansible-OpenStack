# Copyright 2014 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from ironicclient import client as ironic_client
from ironicclient import exc as ironic_exception
import keystoneauth1.session
import mock
from oslo_config import cfg

import nova.conf
from nova import exception
from nova import test
from nova.tests.unit.virt.ironic import utils as ironic_utils
from nova.virt.ironic import client_wrapper

CONF = nova.conf.CONF

FAKE_CLIENT = ironic_utils.FakeClient()


def get_new_fake_client(*args, **kwargs):
    return ironic_utils.FakeClient()


class IronicClientWrapperTestCase(test.NoDBTestCase):

    def setUp(self):
        super(IronicClientWrapperTestCase, self).setUp()
        self.ironicclient = client_wrapper.IronicClientWrapper()
        # Do not waste time sleeping
        cfg.CONF.set_override('api_retry_interval', 0, 'ironic')

    @mock.patch.object(client_wrapper.IronicClientWrapper, '_multi_getattr')
    @mock.patch.object(client_wrapper.IronicClientWrapper, '_get_client')
    def test_call_good_no_args(self, mock_get_client, mock_multi_getattr):
        mock_get_client.return_value = FAKE_CLIENT
        self.ironicclient.call("node.list")
        mock_get_client.assert_called_once_with(retry_on_conflict=True)
        mock_multi_getattr.assert_called_once_with(FAKE_CLIENT, "node.list")
        mock_multi_getattr.return_value.assert_called_once_with()

    @mock.patch.object(client_wrapper.IronicClientWrapper, '_multi_getattr')
    @mock.patch.object(client_wrapper.IronicClientWrapper, '_get_client')
    def test_call_good_with_args(self, mock_get_client, mock_multi_getattr):
        mock_get_client.return_value = FAKE_CLIENT
        self.ironicclient.call("node.list", 'test', associated=True)
        mock_get_client.assert_called_once_with(retry_on_conflict=True)
        mock_multi_getattr.assert_called_once_with(FAKE_CLIENT, "node.list")
        mock_multi_getattr.return_value.assert_called_once_with(
            'test', associated=True)

    @mock.patch.object(keystoneauth1.session, 'Session')
    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_session(self, mock_ir_cli, mock_session):
        """An Ironicclient is called with a keystoneauth1 Session"""
        mock_session.return_value = 'session'
        ironicclient = client_wrapper.IronicClientWrapper()
        # dummy call to have _get_client() called
        ironicclient.call("node.list")
        expected = {'session': 'session',
                    'max_retries': CONF.ironic.api_max_retries,
                    'retry_interval': CONF.ironic.api_retry_interval,
                    'os_ironic_api_version': '1.29',
                    'ironic_url': None}
        mock_ir_cli.assert_called_once_with(1, **expected)

    @mock.patch.object(client_wrapper.IronicClientWrapper, '_multi_getattr')
    @mock.patch.object(client_wrapper.IronicClientWrapper, '_get_client')
    def test_call_fail_exception(self, mock_get_client, mock_multi_getattr):
        test_obj = mock.Mock()
        test_obj.side_effect = ironic_exception.HTTPNotFound
        mock_multi_getattr.return_value = test_obj
        mock_get_client.return_value = FAKE_CLIENT
        self.assertRaises(ironic_exception.HTTPNotFound,
                          self.ironicclient.call, "node.list")

    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_unauthorized(self, mock_get_client):
        mock_get_client.side_effect = ironic_exception.Unauthorized
        self.assertRaises(exception.NovaException,
                          self.ironicclient._get_client)

    @mock.patch.object(ironic_client, 'get_client')
    def test__get_client_unexpected_exception(self, mock_get_client):
        mock_get_client.side_effect = ironic_exception.ConnectionRefused
        self.assertRaises(ironic_exception.ConnectionRefused,
                          self.ironicclient._get_client)

    def test__multi_getattr_good(self):
        response = self.ironicclient._multi_getattr(FAKE_CLIENT, "node.list")
        self.assertEqual(FAKE_CLIENT.node.list, response)

    def test__multi_getattr_fail(self):
        self.assertRaises(AttributeError, self.ironicclient._multi_getattr,
                          FAKE_CLIENT, "nonexistent")

    @mock.patch.object(ironic_client, 'get_client')
    def test__client_is_cached(self, mock_get_client):
        mock_get_client.side_effect = get_new_fake_client
        ironicclient = client_wrapper.IronicClientWrapper()
        first_client = ironicclient._get_client()
        second_client = ironicclient._get_client()
        self.assertEqual(id(first_client), id(second_client))

    @mock.patch.object(ironic_client, 'get_client')
    def test__invalidate_cached_client(self, mock_get_client):
        mock_get_client.side_effect = get_new_fake_client
        ironicclient = client_wrapper.IronicClientWrapper()
        first_client = ironicclient._get_client()
        ironicclient._invalidate_cached_client()
        second_client = ironicclient._get_client()
        self.assertNotEqual(id(first_client), id(second_client))

    @mock.patch.object(ironic_client, 'get_client')
    def test_call_uses_cached_client(self, mock_get_client):
        mock_get_client.side_effect = get_new_fake_client
        ironicclient = client_wrapper.IronicClientWrapper()
        for n in range(0, 4):
            ironicclient.call("node.list")
        self.assertEqual(1, mock_get_client.call_count)