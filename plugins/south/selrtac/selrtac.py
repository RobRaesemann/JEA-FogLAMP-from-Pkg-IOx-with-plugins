""" SELRTAC FogLAMP Plugin

The SELRTAC plugin is split into two Python modules. The SELRTAC module 
contains the functions required of a FogLAMP plugin like plugin_info,
plugin_init, plugin_poll, plugin_reconfigure, and plugin_shutdown. The
selmodus module splits out the Modbus communcations code to make the 
code more modular and easier to maintain and understand.

This SELRTAC module calls get_sel_readings in the selmodbus module to
get the readings from the SELRTAC.

This plugin uses the synchronous methodology for simplicity. FogLAMP also
supports asynchronous operation that could be used for better throughput
if needed.

"""
import copy
import uuid
import json
import logging

from foglamp.common import logger
from foglamp.plugins.common import utils
from foglamp.services.south import exceptions

from foglamp.plugins.south.selrtac.selmodbus import get_sel_readings, close_connection

""" Plugin for reading data from a SELRtac
"""

__author__ = "Rob Raesemann, rob@raesemann.com, +1 904-613-5988"
__copyright__ = "Copyright (c) 2018 JEA"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"

_DEFAULT_CONFIG = {
    'plugin': {
        'description': 'SEL ModBus/TCP South Service Plugin',
        'type': 'string',
        'default': 'selrtac',
        'readonly': 'true'
    },
    'assetName': {
        'description': 'Asset name',
        'type': 'string',
        'default': 'SEL-RTAC',
        'order': "1"
    },
    'pollInterval': {
        'description': 'The interval between poll calls to the device poll routine, expressed in seconds.',
        'type': 'integer',
        'default': '15',
        'order': '2'
    },
    'address': {
        'description': 'Address of Modbus TCP server',
        'type': 'string',
        'default': '127.0.0.1',
        'order': '3'
    },
    'port': {
        'description': 'Port of Modbus TCP server',
        'type': 'integer',
        'default': '502',
        'order': '4'
    },
    'b100_ltc_tank_temp_reg' : {
        'description': 'Register for B100 ltc tank temp',
        'type': 'integer',
        'default': '216',
        'order': '5'
    },
    'b100_top_oil_temp_reg': {
        'description': 'Register for B100 top oil temp',
        'type': 'integer',
        'default': '268',
        'order': '6'
    },    
    'qualitrol_top_oil_temp_reg': {
        'description': 'Register for Qualitrol top oil temp',
        'type': 'integer',
        'default': '520',
        'order': '7'
    },
    'qualitrol_ltc_tank_temp_reg': {
        'description': 'Register for Qualitrol ltc tank temp',
        'type': 'integer',
        'default': '522',
        'order': '8'
    },
    'qualitrol_ltc_tap_position_reg': {
        'description': 'Register for Qualitrol tap changee position',
        'type': 'integer',
        'default': '521',
        'order': '9'
    }

}

_LOGGER = logger.setup(__name__, level=logging.INFO)
""" Setup the access to the logging system of FogLAMP """

UNIT = 1
"""  The slave unit this request is targeting """

pollCounter = 0
""" Counts how many polls have occurred since plugin last sent readings """

def plugin_info():
    """ Returns information about the plugin.

    Args:
    Returns:
        dict: plugin information
    Raises:
    """

    return {
        'name': 'sel',
        'version': '1.0.0',
        'mode': 'poll',
        'type': 'south',
        'interface': '1.0',
        'config': _DEFAULT_CONFIG
    }


def plugin_init(config):
    """ Initialise the plugin.

    Args:
        config: JSON configuration document for the plugin configuration category
    Returns:
        handle: JSON object to be used in future calls to the plugin
    Raises:
    """
    return copy.deepcopy(config)


def plugin_poll(handle):
    """ Poll readings from the modbus device and returns it in a JSON document as a Python dict.

    Available for poll mode only.

    Args:
        handle: handle returned by the plugin initialisation call - i.e. "the config"
    Returns:
        returns a reading in a JSON document, as a Python dict, if it is available
        None - If no reading is available
    Raises:
        DataRetrievalError
    """
    global pollCounter
    """ We don't want to send readings on every poll so we keep track """

    if pollCounter == 0:
        try:
            
            source_address = handle['address']['value']
            source_port = int(handle['port']['value'])
            """ Address and Port are set in the plugin config """
            b100_ltc_tank_temp_reg = int(handle['b100_ltc_tank_temp_reg']['value'])
            b100_top_oil_temp_reg = int(handle['b100_top_oil_temp_reg']['value'])
            qualitrol_top_oil_reg = int(handle['qualitrol_top_oil_temp_reg']['value'])
            qualitrol_ltc_tank_reg = int(handle['qualitrol_ltc_tank_temp_reg']['value'])
            qualitrol_ltc_tap_position_reg = int(handle['qualitrol_ltc_tap_position_reg']['value'])

            readings = get_sel_readings(source_address,source_port, 
                                         b100_ltc_tank_temp_reg,
                                         b100_top_oil_temp_reg,
                                         qualitrol_top_oil_reg,
                                         qualitrol_ltc_tank_reg,
                                         qualitrol_ltc_tap_position_reg)

            wrapper = {
                'asset': handle['assetName']['value'],
                'timestamp': utils.local_timestamp(),
                'key': str(uuid.uuid4()),
                'readings': readings
            }
        except Exception as ex:
            raise exceptions.DataRetrievalError(ex)
        else:
            pollCounter = int(handle['pollInterval']['value'])
            """ reset the pollcounter to the pollInterval plugin setting """
            return wrapper
    else:
        pollCounter -= 1

def plugin_reconfigure(handle, new_config):
    """ Reconfigures the plugin

    it should be called when the configuration of the plugin is changed during the operation of the south service.
    The new configuration category should be passed.

    Args:
        handle: handle returned by the plugin initialisation call
        new_config: JSON object representing the new configuration category for the category
    Returns:
        new_handle: new handle to be used in the future calls
    Raises:
    """

    _LOGGER.info("Old config for SELRTac plugin {} \n new config {}".format(handle, new_config))

    diff = utils.get_diff(handle, new_config)

    if 'address' in diff or 'port' in diff:
        plugin_shutdown(handle)
        new_handle = plugin_init(new_config)
        new_handle['restart'] = 'yes'
        _LOGGER.info("Restarting Modbus TCP plugin due to change in configuration keys [{}]".format(', '.join(diff)))
    else:
        new_handle = copy.deepcopy(new_config)
        new_handle['restart'] = 'no'

    return new_handle


def plugin_shutdown(handle):
    """ Shutdowns the plugin doing required cleanup

    To be called prior to the south service being shut down.

    Args:
        handle: handle returned by the plugin initialisation call
    Returns:
    Raises:
    """
    try:
        return_message = close_connection()
        _LOGGER.info(return_message)
    except Exception as ex:
        _LOGGER.exception('Error in shutting down SELRtac plugin; %s', ex)
        raise
