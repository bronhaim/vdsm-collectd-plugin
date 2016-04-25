# vdsm-collectd-plugin
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; only version 2 of the License is applicable.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# Authors:
#   Yaniv Bronhaim <ybronhei@redhat.com>
#
# About this plugin:
#   This plugin uses collectd's Python plugin to record VDSM statistics.
#
# collectd:
#   http://collectd.org
# oVirt:
#   http://ovirt.org
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml

from vdsm import jsonrpcvdscli
from vdsm.tool import service
import collectd
import signal

VERBOSE_LOGGING = False
CONFIGS = []
client = None


def restore_sigchld():
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)


def configure_callback(conf):
    """Receive configuration block"""
    host = None
    port = None
    auth = None
    instance = None

    for node in conf.children:
        key = node.key.lower()
        val = node.values[0]
        if key == 'host':
            host = val
        elif key == 'port':
            port = int(val)
        elif key == 'auth':
            auth = val
        elif key == 'verbose':
            global VERBOSE_LOGGING
            VERBOSE_LOGGING = bool(node.values[0]) or VERBOSE_LOGGING
        elif key == 'instance':
            instance = val
        else:
            collectd.warning('vdsm_info plugin: Unknown config key: %s.' %
                             key)
            continue

    log('Configured with host=%s, port=%s, instance=%s, using_auth=%s' %
        (host, port, instance, auth is not None))

    CONFIGS.append({'host': host, 'port': port, 'auth': auth,
                    'instance': instance})


def read_callback():
    global client
    if client is None:
        log("for some reason client is still None")
    stats = client.getAllVmStats()
#    info = client.getVdsStats()
#    stats += client.getStorageDomainsList()

    output = {}
    for stat in stats['items']:
        vm_id = stat['vmId']
        output[vm_id] = {}
        output[vm_id]['name'] = stat['vmName']
        output[vm_id]['cpuUsage'] = int(stat['cpuUsage'])
        output[vm_id]['memUsage'] = int(stat['memUsage'])

    for vm_id, _ in output.iteritems():
        for key, val in output[vm_id].iteritems():
            metric = collectd.Values()
            metric.plugin = vm_id
            metric.interval = 10
            metric.type = 'gauge'
            metric.type_instance = key
            metric.values = [val]
            metric.dispatch()


def log(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('VDSM Plugin [verbose]: %s' % msg)


def init_callback():
    restore_sigchld()

    # TODO: add ssl option
    log("Init: Check VDSM availability")
    if service.service_status("vdsmd"):
        log("vdsmd is not running.")
        return

    global client
    client = jsonrpcvdscli.connect('jms.topic.vdsm_requests')
    # TODO: add to jsonrpcvdscli even method registration
    client._client.registerEventCallback(event_recieved)
    # TODO: stop client gently


# doesn't work yet
def event_recieved():
    log("event received")


collectd.register_config(configure_callback)
collectd.register_init(init_callback)

# using default interval each 10sec
collectd.register_read(read_callback)
