VDSM Collectd Plugin
====================

# Description
Using collectd-python library [1] we provide a plugin which can be integrated to
collectd service

# Configuration
To enable plugin modify /etc/collectd.conf to enable python plugin. The
following is an example of how you configure collectd.conf to enable the
plugin (values can be modified to fit the environment):

LoadPlugin python
<Plugin python>
  ModulePath "[path to where you install vdsm_collectd_plugin.py file]"
  LogTraces true
  Interactive true
  Import "vdsm_collectd_plugin"
  <Module vdsm_collectd_plugin">
        host localhost
	port 54321
	instance 'name'
	verbose True
	auth None
  </Module>
</Plugin>

[1] https://collectd.org/documentation/manpages/collectd-python.5.shtml

# Authors
Yaniv Bronhaim <ybronhei@redhat.com>
