# -*- coding: utf-8 -*-
"""
Recording federate

Last Update: 01/29/2023
@author: Anantha Narayanan
anantha.narayanan@nreca.coop
"""

import helics as h
import logging
import sys, csv, json

import math

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG,filename='Recorder_fed_config.log')

setupFile = "simsetup.json"

def destroy_federate(fed):
    '''
    As part of ending a HELICS co-simulation it is good housekeeping to
    formally destroy a federate. Doing so informs the rest of the
    federation that it is no longer a part of the co-simulation and they
    should proceed without it (if applicable). Generally this is done
    when the co-simulation is complete and all federates end execution
    at more or less the same wall-clock time.

    :param fed: Federate to be destroyed
    :return: (none)
    '''
    status = h.helicsFederateFinalize(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()
    logger.info('Federate finalized')


if __name__ == "__main__":

    ##########  Registering  federate and configuring from JSON################
    print("Recorder fed starting...")
    fed = h.helicsCreateValueFederateFromConfig("Recorder_fed_config.json")
    federate_name = h.helicsFederateGetName(fed)
    logger.info(f'Created federate {federate_name}')

    # Diagnostics to confirm JSON config correctly added the required
    #   publication and subscription

    pub_ids = []
    pub_names = []
    for index in range(h.helicsFederateGetPublicationCount(fed)):
        pub_ids.append( h.helicsFederateGetPublicationByIndex(fed, index) )
        pub_names.append( h.helicsPublicationGetKey(pub_ids[index]) )
        logger.debug(f'\tRegistered publication---> {pub_names[index]}')

    sub_ids = []
    sub_names = []
    for index in range(h.helicsFederateGetInputCount(fed)):
        sub_ids.append( h.helicsFederateGetInputByIndex(fed, index) )
        sub_names.append( h.helicsSubscriptionGetKey(sub_ids[index]) )
        logger.debug(f'\tRegistered subscription---> {sub_names[index]}')

    ##############  Entering Execution Mode  ##################################
    logger.debug('Entering HELICS execution mode')
    try:
        h.helicsFederateEnterExecutingMode(fed)
    except:
        logger.debug("Error occurred")
    logger.info('Entered HELICS execution mode')
    logger.debug('Entered HELICS execution mode')

    info = json.load(open(setupFile))
    #total_interval = 10
    total_interval = info["total_interval"]
    update_interval = 1
    grantedtime = 0
    last_freq = 0

    OUTPUT_FILE = 'recorder_data.csv'
    #outputFile = open(OUTPUT_FILE, 'w')
    #writer = csv.writer(outputFile, delimiter=',')

    #newRow = ['timestamp', 'time', 'freq']
    #writer.writerow(newRow)

    LOAD_OUTPUT_FILE = 'output/load_shed_data.csv'
    loadOutputFile = open(LOAD_OUTPUT_FILE, 'w')
    loadWriter = csv.writer(loadOutputFile, delimiter=',')

    switch_status =  "CLOSED"

    dcOutTime = info["dcOutTime"]

    pub_name = "Recorder_fed/diesel_switch_status"
    switch_pub = fed.get_publication_by_name(pub_name)
    main_pub_name = "Recorder_fed/main_switch_status"
    main_switch_pub = fed.get_publication_by_name(main_pub_name)


    shed_loads = []
    loads = info["loads"]
    for load in loads:
        load_pub_name = f"Recorder_fed/{load}"
        load_pub = fed.get_publication_by_name(load_pub_name)
        shed_loads.append(load_pub)

    shed_load_index = 0
    max_shed_loads = len(loads)
    freq_check_time = dcOutTime
    freq_check_incr = info["check_freq_per"]
    freq_drop = info["check_freq_drop"]

    # As long as granted time is in the time range to be simulated...
    while grantedtime < total_interval:
        # Time request for the next physical interval to be simulated
        requested_time = (grantedtime + update_interval)
        grantedtime = h.helicsFederateRequestTime (fed, requested_time)
        if grantedtime >= math.floor(dcOutTime):
            update_interval = 0.02

        freq_sub_name = "gld_fed/gen1_frequency"
        gld_freq_sub = h.helicsFederateGetSubscription(fed, freq_sub_name)
        freq = gld_freq_sub.double/(2 * math.pi)

        if last_freq == 0:
            last_freq = freq

        if grantedtime >= dcOutTime:
            switch_status = "OPEN"
            switch_pub.publish(switch_status)

        if grantedtime >= freq_check_time:
            if freq < last_freq - freq_drop:
                #logger.debug(f'\tChecked freq at {freq_check_time}.')
                #logger.debug(f'\tFreq dropped, trying to shed load.')
                #logger.debug(f'Freq check: {freq} < {last_freq} - {freq_drop}')
                shed_loads[shed_load_index].publish("0")
                logger.debug(f'\tShed load {loads[shed_load_index]}.')
                loadRow = [grantedtime, loads[shed_load_index]]
                loadWriter.writerow(loadRow)
                freq_check_time += freq_check_incr
                shed_load_index += 1
                if shed_load_index >= max_shed_loads:
                    #shed_load_index -= 1
                    raise Exception()
                last_freq = freq

        gld_time_sub_name = "gld_fed/gld_simulation_clock"
        gld_time_sub = h.helicsFederateGetSubscription(fed, gld_time_sub_name)
        gldTime = gld_time_sub.integer      
        
        #newRow = [gldTime, grantedtime, freq]
        #writer.writerow(newRow)

    # Cleaning up HELICS stuff once we've finished the co-simulation.
    destroy_federate(fed)
