
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
import pandas as pd
import math
import csv

# OMF imports
from omf import feeder
from omf.models.voltageDrop import drawPlot
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *

import helics as h
import logging
from functools import reduce

# Model metadata:
modelName, template = __neoMetaModel__.metadata(__file__)
tooltip = 'Simple Microgrid in HELICS'
hidden = False

runnerPath = "/home/ananth/code/NRECA/HELICS/LoadShedding/"
runnerFile = "helics_runner.json"
gen1DataFile = runnerPath + "output/Gen_1_Speed.csv"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG,filename='helicsMG.log')

def work(modelDir, inputDict):
	''' Run the model in its directory. '''
	# Delete output file every run if it exists
	outData = {}		
	# Model operations goes here.

	dcOutTime = inputDict.get("dcOut", 3.01)

	OUTPUT_FILE = 'outages.csv'
	outputFile = open(runnerPath+OUTPUT_FILE, 'w')
	writer = csv.writer(outputFile, delimiter=',')

	newRow = [dcOutTime]
	writer.writerow(newRow)
	outputFile.close()
	
	args = ("helics", "run", f"--path={runnerPath + runnerFile}")
	#proc = subprocess.Popen(args, stdout=subprocess.PIPE)

	grantedtime = 0
	update_interval = 1
	hours = 2
	#total_interval = int(60 * 60 * hours)
	total_interval = 20
	observing = False	
	output = ""
	print("Proc output is: "+output)
	outData["output"] = output

	#Read data from CSV
	df = pd.read_csv(gen1DataFile, skiprows=8, parse_dates=['# timestamp'])
	df.rename(columns={'# timestamp': 'timestamp'}, inplace=True)
	df['rotor_speed'] = df['rotor_speed'].apply(lambda x: x/(2 * math.pi) )

	#Get dropped loads
	shedLoads = pd.read_csv(runnerPath+"output/load_shed_data.csv", names=["time","load"], header=None)
	shedTimes = []
	times=[]
	for t in shedLoads['time']:
		time = pd.to_datetime('2001-08-01 13:00:00') + pd.Timedelta(seconds = t)
		shedTimes.append( time )
		times.append( time.strftime('%H:%M:%S.%f')[:-3] )
	#list(shedLoads["load"])

	outData["shedLoads"] = [{'load': l, 'time': t} for l, t in 
			 				zip(list(shedLoads['load']), times)]
	#utData["shedLoads"] = list(shedLoads["load"])
	#outData["shedTimes"] = shedTimes

	df = pd.read_csv(gen1DataFile, skiprows=8, parse_dates=['# timestamp'])
	df.rename(columns={'# timestamp': 'timestamp'}, inplace=True)

	df['rotor_speed'] = df['rotor_speed'].apply(lambda x: x/(2 * math.pi) )

	shapes=list()
	for t in shedTimes:
		shapes.append({'type': 'line',
					'xref': 'x',
					'yref': 'y',
					'x0': t,
					'y0': df['rotor_speed'].min(),
					'x1': t,
					'y1': df['rotor_speed'].max(),
					'line_color': 'red',
					'line_dash': 'dash'}
					)
	#layout = plotly.graph_objs.Layout(shapes=shapes)

	#fig = go.Figure([go.Scatter(x=df['timestamp'], y=df['rotor_speed'])],layout=layout)

	plotlyLayoutFreq = go.Layout(
		width=1000,
		height=350,
		legend=dict(
			x=0,
			y=1.25,
			orientation="h"),
		shapes=shapes
		)

	plotData = []
	freqPlot = go.Scatter(
		x=df['timestamp'],
		y=df['rotor_speed'],
		line=dict( color=('blue') ),
		name=f"Frequency")
	plotData.append(freqPlot)
	plotlyLayoutFreq['yaxis'].update(title=f'Frequency')
	plotlyLayoutFreq['xaxis'].update(title='Time')
	outData[f"freqPlot"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
	outData[f"freqPlotLayout"] = json.dumps(plotlyLayoutFreq, cls=plotly.utils.PlotlyJSONEncoder)


	#Read data from recorder (freq at meter)
	
	#Diesel generator power output
	plotData = []
	#dgen = []
	plotlyLayoutPower = go.Layout(
		width=1000,
		height=500,
		legend=dict(
			x=0,
			y=1.25,
			orientation="h")
		)
	for i in [1,2,3]:
		dgen =  pd.read_csv(f"{runnerPath}output/Gen_{i}_meter.csv", skiprows=8, parse_dates=['# timestamp'])
		dgenPlot = go.Scatter(
			x=dgen['# timestamp'],
			y=(dgen[' pwr_electric.real'])/1000,
			#line=dict( color=('blue') ),
			name=f"Diesel {i}")
		plotData.append(dgenPlot)


	plotlyLayoutPower['yaxis'].update(title=f'Active Power (kW)')
	plotlyLayoutPower['xaxis'].update(title='Time')
	outData[f"powerPlot"] = json.dumps(plotData, cls=plotly.utils.PlotlyJSONEncoder)
	outData[f"powerPlotLayout"] = json.dumps(plotlyLayoutPower, cls=plotly.utils.PlotlyJSONEncoder)


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
