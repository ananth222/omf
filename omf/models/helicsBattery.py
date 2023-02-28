
from time import time
import warnings
# warnings.filterwarnings("ignore")

import shutil, datetime
from os.path import join as pJoin
import subprocess
import numpy as np
import plotly
import plotly.graph_objs as go
import time

# OMF imports
from omf import feeder
from omf.models.voltageDrop import drawPlot
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *

import helics as h
import logging

# Model metadata:
modelName, template = __neoMetaModel__.metadata(__file__)
tooltip = 'Call helics_player and display HELICS version.'
hidden = False

fileTime = "chargerData_Time.csv"
filePower = "chargeData_Power.csv"
runnerPath = "../helicsModels/Battery/"
runnerFile = "fundamental_default_runner.json"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG,filename='helicsBattery.log')

def work(modelDir, inputDict):
	''' Run the model in its directory. '''
	# Delete output file every run if it exists
	outData = {}		
	# Model operations goes here.

    #fed = h.helicsCreateValueFederateFromConfig("helicsTest.json")
	fedinfo = h.helicsCreateFederateInfo()

	h.helicsFederateInfoSetCoreName(fedinfo, "helicsTest")
	h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
	h.helicsFederateInfoSetFlagOption(fedinfo, h.HELICS_FLAG_OBSERVER, True)
	#h.helicsFederateInfoSetCoreInitString(fedinfo, "--broker=mainbroker --federates=1")
	#h.helicsFederateInfoSetTimeProperty(fedinfo, h.HELICS_PROPERTY_TIME_DELTA, 0.01)

	#inputOne = inputDict.get("input1", 123)
	#inputTwo = inputDict.get("input2", 867)
	#output = inputOne + inputTwo
	battCapacity = []
	battChargeRate = []
	for i in range(5):
		battCapacity.append(int(inputDict[f"b{i+1}Cap"]))
		battChargeRate.append(int(inputDict[f"b{i+1}volts"]))
	np.array(battCapacity).tofile(f"{runnerPath}capacities.csv", ",")
	np.array(battChargeRate).tofile(f"{runnerPath}rates.csv", ",")

	
	args = ("helics", "run", f"--path={runnerPath + runnerFile}")
	proc = subprocess.Popen(args, stdout=subprocess.PIPE)

	fed = h.helicsCreateValueFederate("helicsTest", fedinfo)
	federate_name = h.helicsFederateGetName(fed)
	#print(f'Federate name: {federate_name}')
	logger.info(f'Created federate {federate_name}')
	#h.helicsFederateRegisterSubscription(fed, "Charger/observeme", "string")

	h.helicsFederateEnterExecutingMode(fed)
	logger.info('Entered HELICS execution mode')	

	grantedtime = 0
	update_interval = 60
	hours = 2
	#total_interval = int(60 * 60 * hours)
	total_interval = 300
	observing = True	
	while proc.poll() is None:
		#time.sleep(0.1)
		if observing:
			#print(f'Waiting for co-sim at time {grantedtime}...')
			requested_time = (grantedtime + update_interval)
			grantedtime = h.helicsFederateRequestTime(fed, h.helics_time_maxtime)
			logger.info(f'Waiting in cosim at time {grantedtime}.')
			#sub = h.helicsFederateGetSubscription(fed, "Charger/observeme")
			#obsval = sub.string
			#print(f'Observed value: {obsval}.')
			#if grantedtime > total_interval:
			if grantedtime >= h.helics_time_maxtime:
				print(f'Trying to kill fed.')
				observing = False
				destroy_federate(fed)
		#else:
			#print(f'Waiting for co-sim...')
			#print(f"Reached time {grantedtime}")
			#print("Cosim done!")
	#proc.wait()
	proc_output = proc.stdout.read()
	output = proc_output.decode()
	print("Proc output is: "+output)
	outData["output"] = output

	with open(runnerPath + fileTime, 'rb') as t : timeVals = t.read().decode().split(",")
	with open(runnerPath + filePower, 'rb') as p : powerVals = p.read().decode().split(",")
	outData["timeVals"] = timeVals
	outData["powerVals"] = powerVals
	print(powerVals[:10])

	for i in range(5):
		with open(f"{runnerPath}battery{i}.csv", 'rb') as b : batteryData = b.read().decode().split(",")
		outData[f"battery{i}Data"] = batteryData

	#Battery plots ---------------------------------------------------------------
	for i in range(5):
		plotlyLayoutBattery = go.Layout(
			width=1000,
			height=300,
			legend=dict(
				x=0,
				y=1.25,
				orientation="h")
			)

		plotData = []
		batterySOC = go.Scatter(
			#x=outData["timeVals"],
			#y=outData["powerVals"],
			x=timeVals,
			y=outData[f"battery{i}Data"],
			line=dict( color=('blue') ),
			name=f"Battery {i+1} state of charge")
		plotData.append(batterySOC)
		plotlyLayoutBattery['yaxis'].update(title=f'Battery {i+1} SOC')
		plotlyLayoutBattery['xaxis'].update(title='Time (hours)')
		outData[f"battery{i}SOCData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
		outData[f"battery{i}SOCLayout"] = json.dumps(plotlyLayoutBattery, cls=plotly.utils.PlotlyJSONEncoder)

	#Charger plot ---------------------------------------------------------------
	plotlyLayoutCharger = go.Layout(
		width=1000,
		height=600,
		legend=dict(
			x=0,
			y=1.25,
			orientation="h")
		)

	plotData = []
	powerOut = go.Scatter(
		#x=outData["timeVals"],
		#y=outData["powerVals"],
		x=timeVals,
		y=powerVals,
		line=dict( color=('red') ),
		name="Power drawn by all batteries")
	plotData.append(powerOut)
	plotlyLayoutCharger['yaxis'].update(title='Power Drawn (kW)')
	plotlyLayoutCharger['xaxis'].update(title='Time (hours)')
	outData["powerDrawData"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
	outData["powerDrawLayout"] = json.dumps(plotlyLayoutCharger, cls=plotly.utils.PlotlyJSONEncoder)

	# Model operations typically ends here.
	# Stdout/stderr.
	outData["stdout"] = "Success"
	outData["stderr"] = ""
	return outData

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

def new(modelDir):
	''' Create a new instance of this model. Returns true on success, false on failure. '''
	defaultInputs = {
		"user" : "admin",
		"modelType": modelName,
		"input1": "Input 1",
		"input2": "Input 2",
		"created":str(datetime.datetime.now())
	}
	return __neoMetaModel__.new(modelDir, defaultInputs)

def runtimeEstimate(modelDir):
	''' Estimated runtime of model in minutes. '''
	return 1.0

@neoMetaModel_test_setup
def _tests():
	# Location
	modelLoc = pJoin(__neoMetaModel__._omfDir,"data","Model","admin","Automated Testing of " + modelName)
	# Blow away old test results if necessary.
	try:
		shutil.rmtree(modelLoc)
	except:
		# No previous test results.
		pass
	# Create New.
	new(modelLoc)
	# Pre-run.
	__neoMetaModel__.renderAndShow(modelLoc)
	# Run the model.
	__neoMetaModel__.runForeground(modelLoc)
	# Show the output.
	__neoMetaModel__.renderAndShow(modelLoc)

if __name__ == '__main__':
	_tests()
