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

# Require vdsm installed and running
from vdsm import jsonrpcvdscli
from vdsm.tool import service
import collectd
import re

# Verbose logging on/off. Override in config by specifying 'Verbose'.
VERBOSE_LOGGING = False

CONFIGS = []
VDSM_INFO = {
                'cpuUsage': 'CPU usage',
                'memFree': 'Free memory in hypervisor',
                'cpuIdle': 'CPU idle time',
                'swapFree': 'free swap space',
                'cpuSys': 'whatever',
            }


client = None


def configure_callback(conf):
    """Receive configuration block"""
    host = None
    port = None
    auth = None
    instance = None

    for node in conf.children:
        key = node.key.lower()
        val = node.values[0]
        log('Analyzing config %s key (value: %s)' % (key, val))
        searchObj = re.search(r'vdsm_(.*)$', key, re.M | re.I)

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
#    stats = client.getAllVmStats()
    info = client.getVdsStats()
#    stats += client.getStorageDomainsList()
    # maybe make stats easier to parse?
    #info = parse_info(stats)
    log(info)

    # for now we support only one instance
    conf = CONFIGS[0]
    plugin_instance = conf['instance']
    if plugin_instance is None:
        plugin_instance = '{host}:{port}'.format(host=conf['host'],
                                                 port=conf['port'])

    # currently check only items - status does not relavent
    try:
        #info = info['items'][0]
        # TODO: create VDSM_INFO thing
        for value, description in VDSM_INFO.iteritems():
            #
            try:
                val = collectd.Values(plugin='vdsm_stats')
                val.type = 'bitrate'
                val.type_instance = 'test'
                val.plugin_instance = 'test'
                val.values = [int(info[value])]
                val.dispatch()
                # dispatch_value(info[value], description,
                #               plugin_instance, value)
            except KeyError:
                log(value + ' is not parts of vdsm stats')
    except KeyError:
        # got nothing
        pass


def log(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('VDSM Plugin [verbose]: %s' % msg)


def init_callback():
    # TODO: add ssl option
    # TODO: using one conf for now. maybe we should support listening for more
    # hosts
    log("Init: Check VDSM availability")
    if service.service_status("vdsmd"):
        log("vdsmd is not running.")
        # TODO: what is it was down at first? can we rerun the plugin?
        return
    # maybe add event queue as well?
    global client
    client = jsonrpcvdscli.connect('jms.topic.vdsm_requests')
    # TODO: add to jsonrpcvdscli even method registration
    # client._client.registerEventCallback(event_recieved)
    # TODO: stop client gently


# doesn't work yet
def event_recieved():
    log("Got event")


# register collectd callbacks
collectd.register_config(configure_callback)
collectd.register_init(init_callback)
# using default interval each 10sec
collectd.register_read(read_callback)
