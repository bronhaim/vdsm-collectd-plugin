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
VDSM_INFO = {}


client = None


def fetch_info(conf):
    """Connect to VDSM server and request info"""
    stats = client.getAllVmStats()
    return stats


def parse_info(info_lines):
    """Parse info response from vdsm"""
    info = {}
    for line in info_lines:
        if "" == line or line.startswith('#'):
            continue

        if ':' not in line:
            collectd.warning('vdsm_info plugin: Bad format for info line: %s'
                             % line)
            continue

        key, val = line.split(':')

        # Handle multi-value keys (for dbs and slaves).
        # db lines look like "db0:keys=10,expire=0"
        # slave lines look like "slave0:ip=192.168.0.181,port=6379,state=online
        # ,offset=1650991674247,lag=1"
        if ',' in val:
            split_val = val.split(',')
            for sub_val in split_val:
                k, _, v = sub_val.rpartition('=')
                sub_key = "{0}_{1}".format(key, k)
                info[sub_key] = v
        else:
            info[key] = val

    info["changes_since_last_save"] = info.get("changes_since_last_save",
                                               info.get(
                                                "rdb_changes_since_last_save"))

    return info


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
        elif searchObj:
            log('Matching expression found: key: %s - value: %s' %
                (searchObj.group(1), val))
            global REDIS_INFO
            REDIS_INFO[searchObj.group(1), val] = True
        else:
            collectd.warning('vdsm_info plugin: Unknown config key: %s.' %
                             key)
            continue

    log('Configured with host=%s, port=%s, instance name=%s, using_auth=%s' %
        (host, port, instance, auth is not None))

    CONFIGS.append({'host': host, 'port': port, 'auth': auth,
                    'instance': instance})


def dispatch_value(info, key, type, plugin_instance=None, type_instance=None):
    """Read a key from info response data and dispatch a value"""
    if key not in info:
        collectd.warning('vdsm_info plugin: Info key not found: %s' % key)
        return

    if plugin_instance is None:
        plugin_instance = 'unknown vdsm'
        collectd.error('vdsm_info plugin: plugin_instance is not set, \
                       Info key: %s' % key)

    if not type_instance:
        type_instance = key

    try:
        value = int(info[key])
    except ValueError:
        value = float(info[key])

    log('Sending value: %s=%s' % (type_instance, value))

    val = collectd.Values(plugin='vdsm_stats')
    val.type = type
    val.type_instance = type_instance
    val.plugin_instance = plugin_instance
    val.values = [value]
    val.dispatch()


def read_callback():
    for conf in CONFIGS:
        get_metrics(conf)


def get_metrics(conf):
    info = fetch_info(conf)

    if not info:
        collectd.error('VDSM Plugin: No info received')
        return

    log(info)

    plugin_instance = conf['instance']
    if plugin_instance is None:
        plugin_instance = '{host}:{port}'.format(host=conf['host'],
                                                 port=conf['port'])

    for keyTuple, val in REDIS_INFO.iteritems():
        key, val = keyTuple

        if key == 'total_connections_received' and val == 'counter':
            dispatch_value(info, 'total_connections_received', 'counter',
                           plugin_instance, 'connections_received')
        elif key == 'total_commands_processed' and val == 'counter':
            dispatch_value(info, 'total_commands_processed', 'counter',
                           plugin_instance, 'commands_processed')
        else:
            dispatch_value(info, key, val, plugin_instance)


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
    client = jsonrpcvdscli.connect('jms.topic.vdsm_requests')
    # TODO: add to jsonrpcvdscli even method registration
    client._client.registerEventCallback(event_recieved)
    # TODO: stop client gently


# doesn't work yet
def event_recieved():
    log("Got event")


# register collectd callbacks
collectd.register_config(configure_callback)
collectd.register_init(init_callback)
# using default interval each 10sec
collectd.register_read(read_callback)
